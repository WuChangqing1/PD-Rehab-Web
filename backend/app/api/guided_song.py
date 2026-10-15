from fastapi import APIRouter, Body, File, Form, Query, Response, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import defer
from app.api.deps import CurrentUser, DbSession
from app.core.errors import bad_request, not_found
from app.db.models.guided_song import GuidedSongSession
from app.schemas.guided_song import GuidedSongCreate, GuidedEvents, EmotionStatus
from app.services import guided_song_service as service

router=APIRouter(tags=['Guided song'])


@router.post('/guided-song/sessions',status_code=201)
def create(payload:GuidedSongCreate,db:DbSession,user:CurrentUser):
    return service.detail(service.create_session(db,payload,user.id))


@router.get('/guided-song/sessions/{session_id}')
def read(session_id:str,db:DbSession,user:CurrentUser):
    return service.detail(service.get_session(db,session_id,user.id))


@router.post('/guided-song/sessions/{session_id}/events')
def events(session_id:str,payload:GuidedEvents,db:DbSession,user:CurrentUser):
    return service.detail(service.store_events(db,service.get_session(db,session_id,user.id,True),payload))


@router.post('/guided-song/sessions/{session_id}/segment-2')
def segment_two(session_id:str,db:DbSession,user:CurrentUser):
    return service.detail(service.segment_two(db,service.get_session(db,session_id,user.id,True)))


@router.post('/guided-song/sessions/{session_id}/complete')
def complete(session_id:str,db:DbSession,user:CurrentUser):
    return service.detail(service.finish(db,service.get_session(db,session_id,user.id,True)))


@router.post('/guided-song/sessions/{session_id}/cancel')
def cancel(session_id:str,db:DbSession,user:CurrentUser,payload:GuidedEvents|None=Body(None)):
    row=service.get_session(db,session_id,user.id,True)
    if payload is not None:
        row=service.store_events(db,row,payload)
    return service.detail(service.finish(db,row,True))


@router.post('/guided-song/sessions/{session_id}/audio')
async def audio(session_id:str,db:DbSession,user:CurrentUser,file:UploadFile=File(...),render_version:str=Form('1',max_length=64)):
    row=service.get_session(db,session_id,user.id,True)
    data=await file.read(32*1024*1024+1)
    if len(data)>32*1024*1024: raise bad_request('FILE_TOO_LARGE','音频最大32MB。')
    return service.detail(service.save_audio(db,row,data,render_version))


@router.get('/guided-song/sessions/{session_id}/audio')
def read_audio(session_id:str,db:DbSession,user:CurrentUser):
    row=service.get_session(db,session_id,user.id)
    if not row.audio: raise not_found('尚未保存演奏音频。')
    return Response(row.audio,media_type='audio/wav',headers={'Content-Disposition':f'inline; filename="guided-song-{row.id}.wav"','Cache-Control':'private, no-store'})


@router.get('/patients/{patient_id}/guided-song/history')
def history(patient_id:str,db:DbSession,user:CurrentUser,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
    condition=(GuidedSongSession.patient_id==patient_id,GuidedSongSession.owner_id==user.id)
    total=db.scalar(select(func.count()).select_from(GuidedSongSession).where(*condition))
    rows=db.scalars(select(GuidedSongSession).options(defer(GuidedSongSession.events)).where(*condition).order_by(GuidedSongSession.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[service.detail(r,include_events=False) for r in rows],'total':total,'page':page,'page_size':page_size}

@router.post('/guided-song/sessions/{session_id}/emotion-status')
def emotion_status(session_id:str,payload:EmotionStatus,db:DbSession,user:CurrentUser):
    row=service.get_session(db,session_id,user.id,True)
    if row.status!='ACTIVE':
        return service.detail(row)
    row.config={**row.config,'camera_consent':payload.consent,'camera_transport_status':payload.status}
    db.commit(); db.refresh(row)
    return service.detail(row)
