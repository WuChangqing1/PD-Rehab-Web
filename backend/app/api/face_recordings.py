"""Authenticated, resumable, immutable training-video uploads (protocol 1.2).

No implicit frame approval. The single-process media dispatcher owns decoding.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import shutil
import threading
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import APIError, conflict, not_found
from app.db.base import utcnow
from app.db.models import ExternalPracticeRecord, MobileFaceJob
from app.db.models.face_recording import FaceRecording
from app.services import integration_access as access

def private_response(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(prefix='/integration/v1/face/recordings', tags=['Training face recordings'],
    dependencies=[Depends(private_response)])
CHUNK = 4 * 1024 * 1024
MAX_SIZE = 400 * 1024 * 1024
gate = threading.RLock()
TERMINAL = {'SUCCESS', 'PARTIAL_SUCCESS', 'NO_VALID_SEGMENTS', 'FAILED', 'CANCELLED', 'DELETED'}


def available():
    if not (settings.training_video_enabled and settings.micro_expression_entry == 'causalnet'
            and shutil.which('ffmpeg') and shutil.which('ffprobe')):
        return False
    from app.ml.micro_expression.adapter import analyzer
    return analyzer.refresh_status().is_ready


def root(row):
    # IDs are server UUIDs, never user-controlled paths.
    return settings.upload_path / 'training-face' / str(uuid.UUID(row.id))


def owned(db, user, identifier, *, erase_only=False):
    row = db.get(FaceRecording, str(identifier))
    if row is None: raise not_found('录像任务不存在。')
    access.patient(db, row.patient_id, user)
    if row.operator_id != user.id and user.role != 'ADMIN':
        raise APIError(403, 'FORBIDDEN', '无权读取其他账号的录像。')
    if erase_only:
        return row  # Revoking a device link must not prevent authorized erasure.
    from app.db.models import StaffUser
    operator = db.get(StaffUser, row.operator_id)
    if operator is None or not operator.is_active:
        raise APIError(403, 'FORBIDDEN', '录像账号已停用。')
    access.bound(db, row.device_id, row.local_profile_id, row.patient_id, operator)
    return row


def public(row, *, include_segments=False):
    data = json.loads(row.data_json)
    files = data['manifest']['files']
    uploaded = {}
    for file in files:
        directory = root(row) / file['file_id']
        uploaded[file['file_id']] = (list(range(file['chunk_count'])) if data.get('upload_complete')
            else [i for i in range(file['chunk_count']) if (directory / f'{i}.part').is_file()])
    segments = data.get('segments', [])
    result = dict(recording_id=row.id, status=row.status, external_record_id=row.external_record_id, upload_complete=bool(data.get('upload_complete')),
        uploaded_chunks=uploaded, media_deleted=bool(data.get('media_deleted')), error=data.get('error'), created_at=row.created_at.isoformat() + 'Z',
        expires_at=(min(row.created_at+timedelta(days=7), row.updated_at+timedelta(hours=24))
                    if row.status in TERMINAL else row.created_at+(
                        timedelta(hours=24) if row.status=='UPLOADING' else timedelta(days=7))).isoformat()+'Z',
        summary=f"有效结果 {sum(s['status']=='SUCCESS' for s in segments)} / {len(segments)} 段",
        results=[dict(s.get('result') or {}, source_file_id=s['file_id'], source_start_seconds=s['start_seconds'])
                 for s in segments if s['status']=='SUCCESS'])
    if include_segments:
        result['segments'] = [{k:v for k,v in s.items() if k not in ('stored_path', 'job_id', 'reviewed_by')} for s in segments]
    return result


class VideoFile(BaseModel):
    file_id: uuid.UUID
    sequence: int = Field(ge=0, le=99)
    size_bytes: int = Field(gt=0, le=MAX_SIZE)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    chunk_count: int = Field(ge=1, le=100)
    mime_type: str = Field(pattern=r'^video/mp4$')
    duration_ms: int = Field(gt=0, le=1800000)


class CreateRecording(BaseModel):
    client_capture_id: uuid.UUID
    device_id: str = Field(min_length=8, max_length=100)
    local_profile_id: str = Field(min_length=8, max_length=100)
    patient_id: uuid.UUID
    external_record_id: uuid.UUID
    consent_version: str = Field(pattern=r'^face-capture-v1$')
    agreed_at_ms: int = Field(gt=0)
    files: list[VideoFile] = Field(min_length=1, max_length=100)
    timeline: list[dict] = Field(default_factory=list, max_length=10000)


@router.post('', status_code=201)
def create(payload: CreateRecording, db: DbSession, user: CurrentUser):
    from app.api.integration import limit_request
    limit_request(user,'training-create',6)
    if not available(): raise APIError(503, 'RECORDING_UNAVAILABLE', '训练视频服务尚未配置。')
    access.bound(db,payload.device_id,payload.local_profile_id,str(payload.patient_id),user)
    source=db.get(ExternalPracticeRecord,str(payload.external_record_id))
    if source is None or (source.device_id,source.local_profile_id,source.patient_id,source.operator_id) != (
            payload.device_id,payload.local_profile_id,str(payload.patient_id),user.id) or source.record_type not in (
                'PIANO_SESSION','PIECE_PERFORMANCE','DANCE_SESSION'):
        raise APIError(403,'SOURCE_MISMATCH','录像与训练记录归属不一致。')
    files=payload.files
    if sum(f.size_bytes for f in files)>MAX_SIZE or sum(f.duration_ms for f in files)>1800000:
        raise APIError(413,'FILE_TOO_LARGE','本次录像超过大小或时长限制。')
    if len({f.file_id for f in files})!=len(files) or sorted(f.sequence for f in files)!=list(range(len(files))):
        raise APIError(422,'INVALID_MANIFEST','文件编号或顺序无效。')
    if any(f.chunk_count!=math.ceil(f.size_bytes/CHUNK) for f in files):
        raise APIError(422,'INVALID_MANIFEST','分块数量与文件大小不一致。')
    manifest=payload.model_dump(mode='json')
    try:
        raw=json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (ValueError, RecursionError):
        raise APIError(422,'INVALID_MANIFEST','录像时间线包含无效值。')
    if len(raw.encode())>1024*1024:raise APIError(413,'FILE_TOO_LARGE','录像清单过大。')
    digest=hashlib.sha256(raw.encode()).hexdigest()
    with gate:
        existing=db.scalar(select(FaceRecording).where(FaceRecording.device_id==payload.device_id,
                         FaceRecording.client_capture_id==str(payload.client_capture_id)))
        if existing:
            owned(db,user,existing.id)
            if existing.manifest_sha256!=digest:raise conflict('同一次采集对应不同内容。')
            return public(existing)
        count=db.scalar(select(func.count()).select_from(FaceRecording).where(FaceRecording.status.not_in(TERMINAL)))
        if count>=8:raise APIError(429,'QUEUE_FULL','录像处理队列已满。',headers={'Retry-After':'60'})
        row=FaceRecording(patient_id=str(payload.patient_id),operator_id=user.id,device_id=payload.device_id,
            local_profile_id=payload.local_profile_id,client_capture_id=str(payload.client_capture_id),
            external_record_id=source.id,status='UPLOADING',manifest_sha256=digest,
            data_json=json.dumps({'manifest':manifest,'segments':[]}))
        db.add(row)
        try:db.commit()
        except IntegrityError:db.rollback();raise conflict('录像任务已创建，请重试读取。')
        db.refresh(row);root(row).mkdir(parents=True,exist_ok=True,mode=0o700)
        return public(row)


@router.get('')
def listing(external_record_id:uuid.UUID,db:DbSession,user:CurrentUser):
    source=db.get(ExternalPracticeRecord,str(external_record_id))
    if source is None:raise not_found('训练记录不存在。')
    access.patient(db,source.patient_id,user)
    rows=db.scalars(select(FaceRecording).where(FaceRecording.external_record_id==source.id,
        FaceRecording.status!='DELETED').order_by(FaceRecording.created_at.desc()).limit(100)).all()
    visible=[]
    for row in rows:
        try:visible.append(public(owned(db,user,row.id)))
        except APIError as error:
            if error.status_code not in (403,404):raise
    return {'items':visible}


@router.get('/{recording_id}')
def status(recording_id:uuid.UUID,db:DbSession,user:CurrentUser):
    return public(owned(db,user,recording_id))


@router.put('/{recording_id}/files/{file_id}/chunks/{index}')
async def chunk(recording_id:uuid.UUID,file_id:uuid.UUID,index:int,request:Request,db:DbSession,user:CurrentUser):
    from app.api.integration import limit_request
    limit_request(user,'training-chunk',180)
    row=owned(db,user,recording_id)
    if row.status!='UPLOADING':raise conflict('当前任务不再接收视频。')
    manifest=json.loads(row.data_json)['manifest']
    file=next((f for f in manifest['files'] if f['file_id']==str(file_id)),None)
    if file is None or not 0<=index<file['chunk_count']:raise APIError(422,'INVALID_CHUNK','无效的视频分块。')
    expected=min(CHUNK,file['size_bytes']-index*CHUNK)
    expected_digest=request.headers.get('x-chunk-sha256','')
    if len(expected_digest)!=64:raise APIError(422,'INVALID_CHUNK','缺少分块摘要。')
    directory=root(row)/str(file_id)
    temporary=directory/f'{index}.{uuid.uuid4()}.tmp';final=directory/f'{index}.part'
    size=0;digest=hashlib.sha256()
    try:
        with gate:
            db.expire_all();row=owned(db,user,recording_id)
            if row.status!='UPLOADING':raise conflict('录像已取消或停止接收。')
            directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            target = temporary.open('xb')
        with target:
            os.chmod(temporary,0o600)
            async for block in request.stream():
                size+=len(block)
                if size>expected:raise APIError(413,'FILE_TOO_LARGE','分块超过预定大小。')
                digest.update(block);target.write(block)
        if size!=expected or digest.hexdigest()!=expected_digest:raise APIError(422,'CHUNK_HASH_MISMATCH','分块长度或摘要不一致。')
        with gate:
            db.expire_all();row=owned(db,user,recording_id)
            if row.status!='UPLOADING':raise conflict('录像已取消或停止接收。')
            if final.exists():
                if hashlib.sha256(final.read_bytes()).hexdigest()!=expected_digest:raise conflict('该分块已包含不同内容。')
            else:temporary.replace(final)
        return {'accepted':True,'index':index}
    finally:temporary.unlink(missing_ok=True)


@router.post('/{recording_id}/complete',status_code=202)
def complete(recording_id:uuid.UUID,db:DbSession,user:CurrentUser):
    with gate:
        row=owned(db,user,recording_id)
        if row.status in {'CANCELLED','DELETED','FAILED'}:raise conflict('任务已结束，不能继续提交。')
        if row.status!='UPLOADING':return public(row)
        data=json.loads(row.data_json)
        for file in data['manifest']['files']:
            directory=root(row)/file['file_id'];output=directory/'video.mp4';temporary=directory/'assembling.tmp'
            if not directory.is_dir():raise conflict('视频分块尚未完整上传。')
            digest=hashlib.sha256();size=0
            try:
                with temporary.open('wb') as target:
                    os.chmod(temporary,0o600)
                    for index in range(file['chunk_count']):
                        part=directory/f'{index}.part'
                        if not part.is_file():raise conflict('视频分块尚未完整上传。')
                        with part.open('rb') as source:
                            while block:=source.read(1024*1024):digest.update(block);size+=len(block);target.write(block)
                if size!=file['size_bytes'] or digest.hexdigest()!=file['sha256']:
                    raise APIError(422,'FILE_HASH_MISMATCH','视频完整性校验失败。')
                temporary.replace(output)
            finally:temporary.unlink(missing_ok=True)
        data['upload_complete']=True;row.data_json=json.dumps(data,ensure_ascii=False)
        row.status='PROCESSING';db.commit();db.refresh(row)
        # Keep confirmed chunk indices until successful assembly; complete is idempotent.
        for file in data['manifest']['files']:
            for part in (root(row)/file['file_id']).glob('*.part'):part.unlink(missing_ok=True)
        return public(row)


@router.get('/{recording_id}/segments')
def segments(recording_id:uuid.UUID,db:DbSession,user:CurrentUser,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50)):
    result=public(owned(db,user,recording_id),include_segments=True)
    items=result.pop('segments');return {'items':items[offset:offset+limit],
        'next_offset':offset+limit if offset+limit<len(items) else None}


@router.post('/{recording_id}/retry',status_code=202)
def retry(recording_id:uuid.UUID,db:DbSession,user:CurrentUser):
    with gate:
        row=owned(db,user,recording_id);data=json.loads(row.data_json)
        if row.status not in ('FAILED','PARTIAL_SUCCESS') or not data.get('upload_complete') or data.get('media_deleted'):
            raise conflict('当前录像无法重试分析。')
        if data.get('retry_count',0)>=2 or row.created_at<utcnow()-timedelta(days=7):
            raise conflict('录像重试次数或保留时间已用尽。')
        count=db.scalar(select(func.count()).select_from(FaceRecording).where(FaceRecording.status.not_in(TERMINAL)))
        if count>=8:raise APIError(429,'QUEUE_FULL','录像处理队列已满。',headers={'Retry-After':'60'})
        for segment in data.get('segments',[]):
            if segment['status']=='FAILED':segment['status']='NEW';segment.pop('job_id',None);segment.pop('error',None)
        data['retry_count']=data.get('retry_count',0)+1;data.pop('error',None)
        row.status='PROCESSING';row.data_json=json.dumps(data,ensure_ascii=False);db.commit();db.refresh(row)
        return public(row)


class Review(BaseModel):
    candidate_id:str|None=Field(default=None,max_length=200)
    review_confirmed:bool=False
    reject:bool=False


@router.post('/{recording_id}/segments/{segment_id}/review',status_code=202)
def review(recording_id:uuid.UUID,segment_id:uuid.UUID,payload:Review,db:DbSession,user:CurrentUser):
    with gate:
        row=owned(db,user,recording_id);data=json.loads(row.data_json)
        segment=next((s for s in data['segments'] if s['id']==str(segment_id)),None)
        if row.status in TERMINAL or segment is None or segment['status']!='REVIEW_REQUIRED':raise conflict('当前片段无法复核。')
        if payload.reject:segment['status']='REJECTED'
        else:
            if not payload.review_confirmed:raise APIError(422,'REVIEW_REQUIRED','请先预览并确认关键帧。')
            candidates=segment.get('candidates',[])
            candidate=next((c for c in candidates if str(c['id'])==payload.candidate_id),None)
            if candidate is None:raise APIError(422,'INVALID_CANDIDATE','候选片段已变化，请刷新。')
            indices=[candidate[k] for k in ('onset_frame','apex_frame','offset_frame')]
            if not 1<=indices[0]<indices[1]<indices[2]<=1800:raise APIError(422,'INVALID_CANDIDATE','关键帧无效。')
            count=db.scalar(select(func.count()).select_from(MobileFaceJob).where(MobileFaceJob.status.in_(['PENDING','RUNNING'])))
            if count>=8:raise APIError(429,'QUEUE_FULL','分析队列已满，请稍后复核。',headers={'Retry-After':'60'})
            job=MobileFaceJob(patient_id=row.patient_id,operator_id=row.operator_id,device_id=row.device_id,
                local_profile_id=row.local_profile_id,stored_path=segment['stored_path'],source_filename='training-segment.mp4',
                status='PENDING',indices_json=json.dumps(indices),size_bytes=(settings.upload_path/segment['stored_path']).stat().st_size)
            db.add(job);db.flush();segment['job_id']=job.id;segment['status']='PENDING'
        segment['reviewed_by'] = user.id
        segment['reviewed_at'] = utcnow().isoformat() + 'Z'
        segment['reviewed_candidate_id'] = None if payload.reject else payload.candidate_id
        row.data_json=json.dumps(data,ensure_ascii=False);db.commit();return public(row)


@router.get('/{recording_id}/segments/{segment_id}/frames/{which}')
def frame(recording_id:uuid.UUID,segment_id:uuid.UUID,which:str,db:DbSession,user:CurrentUser,candidate_id:str):
    import subprocess
    from app.services.training_face_jobs import _path, MP4_INPUT
    from app.api.integration import limit_request
    limit_request(user,'training-preview',30)
    row=owned(db,user,recording_id);data=json.loads(row.data_json)
    segment=next((s for s in data['segments'] if s['id']==str(segment_id)),None)
    if segment is None or segment['status']!='REVIEW_REQUIRED':raise not_found('复核画面已失效。')
    candidate=next((c for c in segment.get('candidates',[]) if str(c['id'])==candidate_id),None)
    if candidate is None or which not in ('onset','apex','offset'):raise not_found('候选画面不存在。')
    path=_path(segment['stored_path'])
    if not path.is_relative_to(root(row).resolve()):raise not_found('复核画面已失效。')
    try:
        output=subprocess.run(['ffmpeg','-nostdin','-v','error',*MP4_INPUT,'-i',str(path),'-vf',f"select=eq(n\\,{candidate[which+'_frame']-1}),scale=480:-2",
            '-frames:v','1','-f','image2pipe','-c:v','mjpeg','pipe:1'],capture_output=True,timeout=30,check=True)
    except (OSError, subprocess.SubprocessError):
        raise not_found('复核画面已失效。')
    with gate:
        db.expire_all()
        current=json.loads(owned(db,user,recording_id).data_json)
        if not output.stdout or not any(s['id']==str(segment_id) and s['status']=='REVIEW_REQUIRED' for s in current['segments']):
            raise not_found('复核画面已失效。')
        return Response(output.stdout,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.delete('/{recording_id}')
def delete(recording_id:uuid.UUID,db:DbSession,user:CurrentUser):
    from app.services.training_face_jobs import erase
    with gate:
        row=owned(db,user,recording_id,erase_only=True)
        row.status='DELETED';db.commit()
        erase(db,row)
        return {'deleted':True,'recording_id':row.id}


@router.post('/{recording_id}/cancel')
def cancel(recording_id:uuid.UUID,db:DbSession,user:CurrentUser):
    return delete(recording_id,db,user)
