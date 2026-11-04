"""Bounded single-instance dispatcher for training video decoding and review.

One short segment per pass, alongside the existing inference dispatcher.
"""
from __future__ import annotations
import json
import math
import shutil
import subprocess
import uuid
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select, or_

from app.core.config import settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.db.models import MobileFaceJob, MicroExpressionResult, MediaFile, AssessmentSession, StaffUser
from app.db.models.face_recording import FaceRecording
from app.services import integration_access as access

# Only local MP4 inputs; disallow playlists, network protocols and external MOV data references.
MP4_INPUT = ('-protocol_whitelist', 'file', '-f', 'mov', '-enable_drefs', '0')


def _path(raw):
    path=(settings.upload_path/raw).resolve()
    if not path.is_relative_to(settings.upload_path.resolve()):raise ValueError('invalid media path')
    return path


def erase_job_result(db,job):
    """Only media/results created by this training job, never its practice record."""
    if not job.assessment_session_id:return
    results=db.scalars(select(MicroExpressionResult).where(MicroExpressionResult.assessment_session_id==job.assessment_session_id)).all()
    for result in results:
        media=db.get(MediaFile,result.media_file_id)
        db.delete(result);db.flush()
        if media:
            _path(media.stored_path).unlink(missing_ok=True);db.delete(media)
    db.flush()
    session=db.get(AssessmentSession,job.assessment_session_id)
    if session:db.delete(session)
    job.result_id=None;job.assessment_session_id=None


def erase(db,row,*,media_only=False):
    from app.api.face_recordings import root
    data=json.loads(row.data_json)
    for segment in data.get('segments',[]):
        job=db.get(MobileFaceJob,segment.get('job_id')) if segment.get('job_id') else None
        if job:
            if not media_only or job.status in ('PENDING', 'RUNNING'):
                job.status='CANCELLED';erase_job_result(db,job)
            elif job.assessment_session_id:
                # Keep structured results, remove every owned original-video copy.
                for media in db.scalars(select(MediaFile).where(MediaFile.assessment_session_id==job.assessment_session_id)).all():
                    _path(media.stored_path).unlink(missing_ok=True)
            if job.stored_path:_path(job.stored_path).unlink(missing_ok=True)
            job.stored_path=None
    directory = root(row)
    if directory.exists():
        shutil.rmtree(directory)
    data['media_deleted']=True
    if not media_only:data['segments']=[];data['manifest']['timeline']=[]
    row.data_json=json.dumps(data,ensure_ascii=False);db.commit()


def _check_owner(db, row):
    operator = db.get(StaffUser, row.operator_id, populate_existing=True)
    if operator is None or not operator.is_active:
        raise ValueError('inactive account')
    access.bound(db, row.device_id, row.local_profile_id, row.patient_id, operator)


def run_reviewed_job(db, job_id):
    """Publish only into the authorized parent; never create a generic assessment."""
    from app.api.face_recordings import gate, root, TERMINAL
    from app.ml.micro_expression.adapter import analyzer
    with gate:
        job = db.get(MobileFaceJob, job_id, populate_existing=True)
        if job is None or job.status != 'PENDING' or not job.stored_path:
            return
        parent_id = Path(job.stored_path).parts[1]
        row = db.get(FaceRecording, parent_id, populate_existing=True)
        data = json.loads(row.data_json) if row is not None else {}
        segment = next((item for item in data.get('segments', []) if item.get('job_id') == job_id), None)
        if row is None or row.status in TERMINAL or segment is None or segment['status'] != 'PENDING':
            job.status = 'CANCELLED'
            db.commit()
            return
        try:
            _check_owner(db, row)
            path = _path(job.stored_path)
            if not path.is_relative_to(root(row).resolve()) or not path.is_file():
                raise ValueError('invalid segment media')
            onset, apex, offset = json.loads(job.indices_json)
        except Exception:
            job.status = 'FAILED'
            segment['status'] = 'FAILED'
            segment['error'] = '录像授权或片段已失效。'
            row.status = _status(data)
            row.data_json = json.dumps(data, ensure_ascii=False)
            db.commit()
            return
        job.status = segment['status'] = 'RUNNING'
        row.status = _status(data)
        row.data_json = json.dumps(data, ensure_ascii=False)
        db.commit()
    result = None
    try:
        output = analyzer.analyze(str(path), onset_frame=onset, apex_frame=apex, offset_frame=offset)
        result = {key: output.get(key) for key in (
            'model_name', 'model_version', 'predicted_class', 'dominant_tag',
            'tag_distribution', 'inference_time_ms')}
        result['quality'] = output.get('quality_json')
        json.dumps(result, allow_nan=False)
    except Exception:
        result = None
    with gate:
        db.expire_all()
        job = db.get(MobileFaceJob, job_id)
        row = db.get(FaceRecording, parent_id)
        if job is None or job.status != 'RUNNING' or row is None or row.status in TERMINAL:
            return
        data = json.loads(row.data_json)
        segment = next((item for item in data['segments'] if item.get('job_id') == job_id), None)
        if segment is None:
            return
        try:
            _check_owner(db, row)
        except Exception:
            result = None
        job.status = segment['status'] = 'SUCCESS' if result is not None else 'FAILED'
        if result is not None:
            segment['result'] = result
        else:
            segment['error'] = '该片段未能完成分析。'
        row.status = _status(data)
        row.data_json = json.dumps(data, ensure_ascii=False)
        db.commit()


def _probe(path):
    response=subprocess.run(['ffprobe','-v','error',*MP4_INPUT,'-select_streams','v:0','-show_entries',
        'stream=codec_name,width,height,avg_frame_rate:format=duration','-of','json',str(path)],
        capture_output=True,check=True,timeout=30)
    value=json.loads(response.stdout);video=value['streams'][0]
    numerator,denominator=video['avg_frame_rate'].split('/')
    fps=float(numerator)/float(denominator);duration=float(value['format']['duration'])
    if not math.isfinite(fps) or not 1<=fps<=240 or not math.isfinite(duration) or not 0<duration<=1805:
        raise ValueError('invalid duration or fps')
    if video['width']*video['height']>3840*2160:raise ValueError('resolution limit')
    return fps,duration


def _status(data):
    segments=data.get('segments',[])
    if not segments:return 'NO_VALID_SEGMENTS'
    if any(s['status']=='NEW' for s in segments):return 'PROCESSING'
    if any(s['status']=='REVIEW_REQUIRED' for s in segments):return 'REVIEW_REQUIRED'
    if any(s['status'] in ('PENDING','RUNNING') for s in segments):return 'RUNNING'
    successes=sum(s['status']=='SUCCESS' for s in segments)
    if successes:return 'SUCCESS' if successes==len(segments) else 'PARTIAL_SUCCESS'
    return 'FAILED' if any(s['status']=='FAILED' for s in segments) else 'NO_VALID_SEGMENTS'


def step():
    from app.api.face_recordings import root,gate,TERMINAL
    from app.ml.micro_expression.adapter import analyzer
    with SessionLocal() as db:
        rows=db.scalars(select(FaceRecording).where(or_(FaceRecording.status.not_in(TERMINAL),
            ((FaceRecording.updated_at < utcnow()-timedelta(hours=24)) | (FaceRecording.status=='DELETED'))
            & ~FaceRecording.data_json.contains('"media_deleted": true'))).order_by(FaceRecording.created_at)).all()
        for row in rows:
            prepared_segments=None;preparation_error=False
            snapshot=json.loads(row.data_json)
            if row.status=='PROCESSING' and not snapshot.get('segments'):
                # Probing may be slow; cancellation and chunk transfers keep their API lock.
                try:
                    prepared_segments=[]
                    total_duration = 0.0
                    for file in snapshot['manifest']['files']:
                        fps,duration=_probe(root(row)/file['file_id']/'video.mp4')
                        total_duration += duration
                        if total_duration > 1805:
                            raise ValueError('recording exceeds total duration limit')
                        interval=min(20.0,1700.0/fps);start=0.0
                        while start<duration:
                            length=min(interval,duration-start)
                            if length<1:break
                            ident=str(uuid.uuid4())
                            prepared_segments.append(dict(id=ident,file_id=file['file_id'],start_seconds=start,
                                duration_seconds=length,fps=fps,status='NEW',
                                stored_path=str((root(row)/f'{ident}.mp4').relative_to(settings.upload_path))))
                            start+=max(1,interval-1)
                except Exception:preparation_error=True
            with gate:
                db.expire_all();row=db.get(FaceRecording,row.id)
                if row is None:continue
                data=json.loads(row.data_json)
                if row.created_at<utcnow()-(timedelta(hours=24) if row.status=='UPLOADING' else timedelta(days=7)) and row.status not in TERMINAL:
                    row.status='FAILED';data['error']='录像等待超时。';row.data_json=json.dumps(data);erase(db,row,media_only=True);continue
                if row.status in TERMINAL:
                    if not data.get('media_deleted') and (row.status=='DELETED' or row.updated_at<utcnow()-timedelta(hours=24)):
                        erase(db,row,media_only=row.status!='DELETED')
                    continue
                if row.status=='UPLOADING':continue
                try:
                    _check_owner(db,row)
                except Exception:
                    row.status='FAILED';data['error']='录像授权已失效。';row.data_json=json.dumps(data);erase(db,row,media_only=True);continue
                if not data.get('segments'):
                    if preparation_error:
                        row.status='FAILED';data['error']='录像格式或解码检查未通过。';row.data_json=json.dumps(data);db.commit();continue
                    if prepared_segments is None:continue
                    data['segments']=prepared_segments
                    row.data_json=json.dumps(data);db.commit()
                # Reconcile completed child jobs without rewriting raw practice metrics.
                for segment in data['segments']:
                    if not segment.get('job_id'):continue
                    job=db.get(MobileFaceJob,segment['job_id'],populate_existing=True)
                    if job:
                        segment['status']=job.status
                row.status=_status(data);row.data_json=json.dumps(data,ensure_ascii=False);db.commit()
                pending=next((s for s in data['segments'] if s['status']=='NEW'),None)
                if pending is None:continue
            # Expensive decoding happens outside the API lock. Cancellation wins on publication.
            try:
                source=root(row)/pending['file_id']/'video.mp4';target=_path(pending['stored_path'])
                subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-ss',str(pending['start_seconds']),*MP4_INPUT,'-i',str(source),
                    '-t',str(pending['duration_seconds']),'-map','0:v:0','-an','-sn','-dn','-vf','scale=720:-2','-vsync','0',
                    '-c:v','libx264','-crf','18',str(target)],capture_output=True,check=True,timeout=120)
                target.chmod(0o600)
                result=analyzer.spot(str(target))
                candidates=result.get('candidates',[])
                pending['candidates']=candidates
                pending['status']='REVIEW_REQUIRED' if candidates else 'NO_VALID_SEGMENTS'
                # No candidate or classifier score is ever used as automatic consent.
            except Exception:
                pending['status']='FAILED';pending['error']='该片段未能完成候选定位。'
            with gate:
                db.expire_all();fresh=db.get(FaceRecording,row.id)
                if fresh is None or fresh.status in ('DELETED','CANCELLED'):
                    _path(pending['stored_path']).unlink(missing_ok=True);return True
                # Preserve reviews submitted while this segment was decoded.
                latest=json.loads(fresh.data_json)
                for segment in latest['segments']:
                    if segment['id']==pending['id']:segment.update(pending)
                fresh.status=_status(latest);fresh.data_json=json.dumps(latest,ensure_ascii=False);db.commit()
            return True
    return False
