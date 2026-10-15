"""First-message authenticated live channel; raw video is never persisted."""
import asyncio
import json
import uuid
import time
from app.services import live_emotion_service as service
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.deps import DbSession
from app.core.errors import APIError
from app.core.security import decode_access_token
from app.db.models import Patient, StaffUser
from app.db.models.guided_song import GuidedSongSession
from app.services.live_emotion_service import capabilities, simulation_enabled, simulation_result, remember_result

router = APIRouter(prefix='/live-emotion', tags=['live-emotion'])
_connections: set[str] = set()
AUTH_TIMEOUT = 5
INFERENCE_TIMEOUT = 10

@router.websocket('/stream')
async def stream(ws: WebSocket, db: DbSession):
    # A token is deliberately never accepted from the URL or logs.
    await ws.accept()
    owner = None
    registered = False
    adapter = None
    decoder = None
    worker = None
    try:
        raw = await asyncio.wait_for(ws.receive_text(), AUTH_TIMEOUT)
        if len(raw) > 8192: raise ValueError('AUTH_SIZE_LIMIT')
        hello = json.loads(raw)
        if not isinstance(hello,dict) or hello.get('type') != 'auth': raise ValueError('AUTH_REQUIRED')
        payload = decode_access_token(hello.get('token',''))
        owner = str(payload['sub'])
        user = db.get(StaffUser, owner)
        session = db.get(GuidedSongSession, str(hello.get('session_id','')))
        patient = db.get(Patient, str(hello.get('patient_id','')))
        if not user or not user.is_active or not session or not patient or patient.is_deleted:
            raise ValueError('NOT_AUTHORIZED')
        if session.owner_id != owner or session.patient_id != patient.id or session.status != 'ACTIVE':
            raise ValueError('NOT_AUTHORIZED')
        if owner in _connections or len(_connections) >= 16: raise ValueError('CONNECTION_LIMIT')
        _connections.add(owner)
        registered = True
        stream_id = str(uuid.uuid4())
        if simulation_enabled() and getattr(session,'is_simulation',False) and hello.get('simulation_demo') is True:
            result = simulation_result(session.id,patient.id) | {'stream_id':stream_id}
            remember_result(result)
            await ws.send_json(result)
        else:
            adapter = service.verified_adapter()
            if adapter is None:
                await ws.send_json(capabilities() | {'type':'status', 'stream_id':stream_id,
                                                    'session_id':session.id,'patient_id':patient.id})
                await ws.close(code=1000)
                return
            decoder = adapter.open()
            await ws.send_json(dict(type='status',status='READY',capture_required=True,
                                    protocol='continuous-mediarecorder-v1',stream_id=stream_id,
                                    session_id=session.id,patient_id=patient.id,requirements=adapter.requirements,
                                    model_name=adapter.model_name,model_version=adapter.model_version))
            guard = service.StreamGuard()
            previous_end = None
            previous_mime = None
            while True:
                text = await asyncio.wait_for(ws.receive_text(), 15)
                if len(text)>8192: raise ValueError('MESSAGE_SIZE_LIMIT')
                metadata = json.loads(text)
                if not isinstance(metadata,dict) or metadata.get('type')!='chunk': raise ValueError('PROTOCOL')
                mime = metadata.get('mime_type')
                if mime not in ('video/webm','video/webm;codecs=vp8','video/mp4') or (previous_mime and previous_mime!=mime):
                    raise ValueError('ENCODING')
                guard.begin(metadata)
                if previous_end is not None and abs(metadata['capture_timestamp_ms']-previous_end)>250:
                    raise ValueError('DISCONTINUITY')
                chunk = await asyncio.wait_for(ws.receive_bytes(), 5)
                guard.finish(len(chunk))
                db.refresh(session)
                db.refresh(user)
                db.refresh(patient)
                if session.status!='ACTIVE' or not user.is_active or patient.is_deleted: raise ValueError('SESSION_ENDED')
                # One worker per stream, no inference queue. The shared GPU lock
                # also serializes this work with existing file-based analysis.
                worker = asyncio.create_task(asyncio.to_thread(service.infer_chunk,adapter,decoder,chunk,metadata))
                result = await asyncio.wait_for(asyncio.shield(worker), INFERENCE_TIMEOUT)
                worker = None
                result |= dict(type='result',session_id=session.id,patient_id=patient.id,stream_id=stream_id,
                               capture_timestamp_ms=metadata['capture_timestamp_ms'],result_timestamp_ms=int(time.time()*1000),
                               seq=metadata['seq'],model_name=adapter.model_name,model_version=adapter.model_version,
                               labels=service.LABELS,source='MODEL',clinical_eligible=False)
                service.remember_result(result)
                await ws.send_json(result)
                await ws.send_json(dict(type='ack',seq=metadata['seq']))
                previous_end = metadata['capture_timestamp_ms']+metadata['duration_ms']
                previous_mime = mime
        await ws.close(code=1000)
    except asyncio.TimeoutError:
        await ws.close(code=4408, reason='STREAM_TIMEOUT' if registered else 'AUTH_TIMEOUT')
    except (ValueError, TypeError, APIError):
        await ws.close(code=4403, reason='NOT_AUTHORIZED')
    except WebSocketDisconnect:
        pass
    finally:
        try:
            # A timed-out native inference cannot safely be killed mid-call.
            # Close transport immediately; keep its one worker bounded and wait
            # for it before releasing decoder state and the connection slot.
            if worker is not None:
                try: await worker
                except Exception: pass
            if adapter is not None and decoder is not None:
                await asyncio.to_thread(adapter.close, decoder)
        finally:
            if registered: _connections.discard(owner)
