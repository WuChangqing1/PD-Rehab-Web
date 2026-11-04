"""Single-instance durable mobile face dispatcher for the existing one-worker service.

PENDING indices survive restart. Interrupted RUNNING tasks fail explicitly;
committed completed results are reconciled before failure. No nested ML lock.
"""
import asyncio,json,logging
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select,update
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.errors import APIError,ErrorCode
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.db.models import MobileFaceJob,StaffUser,AssessmentSession,MicroExpressionResult
from app.services import integration_access as access
logger=logging.getLogger(__name__)

def path_for(job):
    if not job.stored_path:return None
    path=(settings.upload_path/job.stored_path).resolve()
    if not path.is_relative_to(settings.upload_path.resolve()):raise ValueError('invalid mobile upload path')
    return path

def erase_video(job):
    if job.stored_path and Path(job.stored_path).parts[0] == 'training-face':
        return  # The parent owns retention and retry for the segment.
    path=path_for(job)
    if path:path.unlink(missing_ok=True)
    job.stored_path=None

def fail_job(db,job,code,message,*,reconcile=True):
    # If analysis already committed, reconcile instead of losing a valid result.
    result=db.scalar(select(MicroExpressionResult).where(MicroExpressionResult.assessment_session_id==job.assessment_session_id)) if job.assessment_session_id else None
    if result and reconcile:
        job.result_id=result.id;job.status='SUCCESS';job.error_code=None;job.error_message=None
    else:
        job.status='FAILED';job.error_code=code;job.error_message=message
        if job.assessment_session_id:
            from app.services.assessment_service import delete_session
            session=db.get(AssessmentSession,job.assessment_session_id)
            if session and session.status!='COMPLETED':delete_session(db,session.id,job.patient_id)
            job.assessment_session_id=None
    erase_video(job);db.commit()

def recover_jobs():
    with SessionLocal() as db:
        for job in db.scalars(select(MobileFaceJob).where(MobileFaceJob.status.in_(['UPLOADING','RUNNING']))).all():
            fail_job(db,job,'TASK_INTERRUPTED','服务中断，请重新提交视频。')
    expire_jobs()

def expire_jobs():
    with SessionLocal() as db:
        stale=utcnow()-timedelta(hours=24)
        jobs=db.scalars(select(MobileFaceJob).where(MobileFaceJob.status.in_(['REVIEW_REQUIRED','PENDING']),MobileFaceJob.created_at<stale)).all()
        for job in jobs:fail_job(db,job,'REVIEW_EXPIRED','视频等待超时，请重新提交。')

def run_face(job_id):
    from app.schemas.assessment import AssessmentSessionCreate,MicroExpressionAnalyzeRequest
    from app.services import assessment_service
    from app.ml.micro_expression.adapter import analyzer
    with SessionLocal() as db:
        candidate = db.get(MobileFaceJob, job_id)
        if candidate and candidate.stored_path and Path(candidate.stored_path).parts[0] == 'training-face':
            from app.services.training_face_jobs import run_reviewed_job
            run_reviewed_job(db, job_id)
            return
        claimed=db.execute(update(MobileFaceJob).where(MobileFaceJob.id==job_id,MobileFaceJob.status=='PENDING').values(status='RUNNING',updated_at=utcnow()))
        if claimed.rowcount!=1:db.rollback();return
        db.commit();job=db.get(MobileFaceJob,job_id)
        try:
            user=db.get(StaffUser,job.operator_id)
            if user is None or not user.is_active:raise APIError(403,ErrorCode.FORBIDDEN,'账号已停用。')
            access.bound(db,job.device_id,job.local_profile_id,job.patient_id,user)
            path=path_for(job)
            if path is None or not path.is_file():raise APIError(404,ErrorCode.NOT_FOUND,'视频已失效。')
            if not analyzer.refresh_status().is_ready:raise APIError(503,ErrorCode.MODEL_UNAVAILABLE,'面部模型不可用。')
            indices=json.loads(job.indices_json) if job.indices_json else None
            if settings.micro_expression_entry=='causalnet' and not indices:raise ValueError('missing reviewed indices')
            session=assessment_service.create_session(db,job.patient_id,AssessmentSessionCreate(session_type='MICRO_EXPRESSION_ONLY'),created_by=user.id)
            job.assessment_session_id=session.id;db.commit()
            payload=MicroExpressionAnalyzeRequest(onset_frame=indices[0] if indices else None,apex_frame=indices[1] if indices else None,offset_frame=indices[2] if indices else None,selection_source='MANUAL',review_confirmed=bool(indices))
            # CausalNetRuntime acquires the process/global inference locks itself.
            result,_=assessment_service.analyze_micro_expression(db,session.id,patient_id=job.patient_id,original_filename=job.source_filename,content=path.read_bytes(),payload=payload,created_by=user.id)
            # Re-check permission before publishing after slow inference.
            db.expire_all();access.bound(db,job.device_id,job.local_profile_id,job.patient_id,user)
            job=db.get(MobileFaceJob,job_id)
            job.result_id=result.id;job.status='SUCCESS'
            erase_video(job);db.commit()
        except Exception as exc:
            db.rollback();job=db.get(MobileFaceJob,job_id)
            if job:fail_job(db,job,str(getattr(exc,'code','INFERENCE_FAILED'))[:80],str(getattr(exc,'message','面部视频分析未成功，请重新录制。'))[:500],reconcile=not (isinstance(exc,APIError) and exc.status_code==403))
            logger.warning('mobile face task ended: %s',type(exc).__name__)

def process_next():
    with SessionLocal() as db:
        ident=db.scalar(select(MobileFaceJob.id).where(MobileFaceJob.status=='PENDING').order_by(MobileFaceJob.created_at,MobileFaceJob.id).limit(1))
    if ident:run_face(ident)
    return bool(ident)

async def dispatcher_loop():
    last=0
    while True:
        try:
            now=asyncio.get_running_loop().time()
            if now-last>60:await run_in_threadpool(expire_jobs);last=now
            had=await run_in_threadpool(process_next)
            if settings.training_video_enabled:
                from app.services.training_face_jobs import step
                had = await run_in_threadpool(step) or had
            if not had:await asyncio.sleep(1)
        except asyncio.CancelledError:raise
        except Exception:
            logger.exception('mobile dispatcher error')
            await asyncio.sleep(5)
