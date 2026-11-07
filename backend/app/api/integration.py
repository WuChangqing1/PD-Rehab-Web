"""Authenticated Flutter/Web integration API, v1.

Cross-client records intentionally do not get cast into piano_sessions. Their
native metric semantics and provenance are retained until a verified metric
mapping exists. Every write is bound to a chosen server patient ID.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.db.base import utcnow
from app.db.models import (Patient, StaffUser, AssessmentSession,
    DevicePatientLink, ExternalPracticeRecord, MobileFaceJob, ExpertChatTurn)
from app.db.session import SessionLocal

from app.services import integration_access as access

router = APIRouter(prefix="/integration/v1", tags=["Cross-client integration"])


def _patient(db, patient_id: str) -> Patient:
    row = db.get(Patient, patient_id)
    if row is None or row.is_deleted:
        raise not_found("患者不存在或已停用，请重新选择。")
    return row


def _bound(db, device_id, profile_id, patient_id, user):
    return access.bound(db,device_id,profile_id,patient_id,user)

_admission=threading.Lock()
_limits=defaultdict(deque)
_limit_lock=threading.Lock()
def limit_request(user,key,maximum):
    now=time.monotonic()
    with _limit_lock:
        queue=_limits[(user.id,key)]
        while queue and queue[0]<now-60:queue.popleft()
        if len(queue)>=maximum:
            raise APIError(429,'RATE_LIMITED','请求较频繁，请稍后重试。',headers={'Retry-After':'60'})
        queue.append(now)
        if len(_limits)>10000:
            for old in list(_limits):
                if not _limits[old] or _limits[old][-1]<now-60:del _limits[old]


class BindRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=100)
    local_profile_id: str = Field(min_length=8, max_length=100)
    patient_id: str = Field(min_length=36, max_length=36)


class ExternalRecordIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=100)
    local_profile_id: str = Field(min_length=8, max_length=100)
    patient_id: str = Field(min_length=36, max_length=36)
    source_record_id: str = Field(min_length=1, max_length=100)
    record_type: str = Field(pattern=r"^(PIANO_SESSION|PIECE_PERFORMANCE|DANCE_SESSION|TRAINING_PLAN|TRAINING_PLAN_EVENT|OTHER)$")
    schema_version: str = Field(min_length=1, max_length=32)
    task_version: str | None = Field(default=None, max_length=80)
    metric_version: str | None = Field(default=None, max_length=80)
    captured_at_ms: int | None = Field(default=None, ge=0)
    payload: dict = Field(default_factory=dict)


def _record_out(row: ExternalPracticeRecord, *, include_payload: bool = False) -> dict:
    result = dict(id=row.id, patient_id=row.patient_id, operator_id=row.operator_id,
        device_id=row.device_id, local_profile_id=row.local_profile_id, source_record_id=row.source_record_id,
        record_type=row.record_type, schema_version=row.schema_version,
        task_version=row.task_version, metric_version=row.metric_version,
        captured_at_ms=row.captured_at_ms, created_at=row.created_at.isoformat(),
        payload_sha256=row.payload_sha256, origin=row.origin)
    result["received_at"] = row.created_at.isoformat() + "Z" if row.created_at.tzinfo is None else row.created_at.isoformat()
    if include_payload:
        result["payload"] = json.loads(row.payload_json)
    return result


@router.get("/bootstrap")
def bootstrap(db: DbSession, user: CurrentUser,
              limit: int = Query(100, ge=1, le=200),
              offset: int = Query(0, ge=0)) -> dict:
    """Explicitly bounded staff/patient snapshot; never returns passwords."""
    patients = db.scalars(select(Patient).where(access.scope(db,user)).order_by(Patient.created_at, Patient.id)
                          .limit(limit).offset(offset)).all()
    staff = db.scalars(select(StaffUser).where(StaffUser.is_active.is_(True), StaffUser.role.in_(['ADMIN', 'DOCTOR']))
                       .order_by(StaffUser.display_name).limit(200)).all()
    if user.role == 'PATIENT':
        staff = []  # Ordinary accounts never download the staff directory.
    return {"schema_version": "1.0", "user": {"id": user.id, "display_name": user.display_name},
            "patients": [{"id": p.id, "hospital_number": p.hospital_number,
                          "name": p.name, "sex": p.sex, "birthday": p.birthday.isoformat() if p.birthday else None,
                          "medication_state": p.medication_state, "is_deleted": p.is_deleted,
                          "updated_at": p.updated_at.isoformat()} for p in patients],
            "staff": [{"id": s.id, "display_name": s.display_name} for s in staff],
            "next_offset": offset + len(patients) if len(patients) == limit else None}


@router.post("/bindings")
def bind_profile(payload: BindRequest, db: DbSession, user: CurrentUser) -> dict:
    patient = access.patient(db, payload.patient_id,user)
    link = db.scalar(select(DevicePatientLink).where(
        DevicePatientLink.device_id == payload.device_id,
        DevicePatientLink.local_profile_id == payload.local_profile_id))
    if link and (link.bound_by!=user.id or not link.active):
        raise APIError(403,ErrorCode.FORBIDDEN,'此设备档案不属于当前账号或绑定已撤销。')
    if link and link.patient_id != payload.patient_id:
        # Changing an existing binding needs a separate explicit revoke flow;
        # never silently reattribute the previous patient's local sessions.
        raise conflict("此设备档案已绑定其他患者，不能直接覆盖；请使用新档案或联系维护人员处理解绑。")
    if not link:
        link = DevicePatientLink(device_id=payload.device_id, local_profile_id=payload.local_profile_id,
                                 patient_id=patient.id, bound_by=user.id)
        db.add(link)
        try: db.commit()
        except IntegrityError:
            db.rollback()
            # Concurrent bind must be reconciled, not silently assumed successful.
            raise conflict("绑定状态已变化，请刷新后重试。")
        db.refresh(link)
    return {"binding_id": link.id, "patient_id": patient.id,
            "hospital_number": patient.hospital_number, "name": patient.name}


@router.post("/records", status_code=201)
def sync_record(payload: ExternalRecordIn, db: DbSession, user: CurrentUser) -> dict:
    _bound(db, payload.device_id, payload.local_profile_id, payload.patient_id,user)
    limit_request(user,'sync',120)
    raw = json.dumps(payload.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(raw.encode("utf-8")) > 8 * 1024 * 1024:
        raise APIError(413, ErrorCode.FILE_TOO_LARGE, "单条记录超过 8 MB 上限。")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    stmt = select(ExternalPracticeRecord).where(
        ExternalPracticeRecord.device_id == payload.device_id,
        ExternalPracticeRecord.source_record_id == payload.source_record_id,
        ExternalPracticeRecord.record_type == payload.record_type)
    existing = db.scalar(stmt)
    if existing:
        if (existing.payload_sha256 != digest or existing.patient_id != payload.patient_id or
            existing.schema_version != payload.schema_version or existing.local_profile_id != payload.local_profile_id or
            existing.task_version != payload.task_version or existing.metric_version != payload.metric_version or existing.captured_at_ms != payload.captured_at_ms):
            raise conflict("相同来源记录 ID 对应不同内容，拒绝覆盖。")
        return {**_record_out(existing), "already_synced": True}
    row = ExternalPracticeRecord(patient_id=payload.patient_id,operator_id=user.id,
        device_id=payload.device_id, local_profile_id=payload.local_profile_id, source_record_id=payload.source_record_id,
        record_type=payload.record_type, schema_version=payload.schema_version,
        task_version=payload.task_version, metric_version=payload.metric_version,
        captured_at_ms=payload.captured_at_ms, payload_sha256=digest,
        payload_json=raw, origin="PianoForParkinson")
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(stmt)
        if existing and all(getattr(existing,key)==getattr(payload,key) for key in
            ('patient_id','local_profile_id','schema_version','task_version','metric_version','captured_at_ms')) and existing.payload_sha256==digest:
            return {**_record_out(existing), "already_synced": True}
        raise conflict("并发同步记录冲突，请检查记录来源。")
    db.refresh(row)
    return {**_record_out(row), "already_synced": False}


@router.get("/records")
def list_records(patient_id: str, db: DbSession, user: CurrentUser,
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 include_payload: bool = False, exclude_plan_snapshots: bool = False) -> dict:
    access.patient(db, patient_id,user)
    query = select(ExternalPracticeRecord).where(ExternalPracticeRecord.patient_id == patient_id)
    if exclude_plan_snapshots:
        query = query.where(ExternalPracticeRecord.record_type != "TRAINING_PLAN")
    rows = db.scalars(query
        .order_by(ExternalPracticeRecord.created_at.desc(), ExternalPracticeRecord.id.desc())
        .limit(limit).offset(offset)).all()
    return {"items": [_record_out(row, include_payload=include_payload) for row in rows],
            "next_offset": offset + len(rows) if len(rows) == limit else None}


def _plan_preview(row, on_date: date) -> tuple[tuple, dict]:
    payload = json.loads(row.payload_json)
    record = payload.get("record")
    record = record if isinstance(record, dict) else {}
    plan = record.get("plan_json")
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except ValueError:
            plan = None
    plan = plan if isinstance(plan, dict) else {}
    plan_id = record.get("plan_id")
    # Never merge records without a trustworthy device/profile/plan identity.
    key = (row.device_id, row.local_profile_id, plan_id) if (
        row.local_profile_id and isinstance(plan_id, str) and plan_id
    ) else (row.id,)
    revision = payload.get("snapshot_revision")
    revision = revision if type(revision) is int and revision >= 0 else None
    daily = payload.get("daily_progress")
    progress = None
    if isinstance(daily, list):
        for entry in daily:
            if not isinstance(entry, dict) or entry.get("local_date") != on_date.isoformat():
                continue
            units, target = entry.get("completed_units"), entry.get("target")
            if (entry.get("target_type") in ("count", "minutes") and
                type(units) in (int, float) and 0 <= units <= 10**12 and
                type(target) in (int, float) and 0 < target <= 10**12):
                progress = {k: entry[k] for k in ("local_date", "target_type", "completed_units", "target")}
            break
    start = plan.get("start")
    try:
        start = date.fromisoformat(start).isoformat() if isinstance(start, str) else None
    except ValueError:
        start = None
    title = plan.get("title")
    return key, {**_record_out(row), "title": title[:160] if isinstance(title, str) else None,
                 "plan_start": start, "snapshot_revision": revision, "progress": progress}


@router.get("/plans")
def list_plan_snapshots(patient_id: str, on_date: date, db: DbSession, user: CurrentUser,
                        snapshot_id: str | None = None, limit: int = Query(30, ge=1, le=100),
                        offset: int = Query(0, ge=0)) -> dict:
    """Group before pagination; retain original records and the v1 record API."""
    access.patient(db, patient_id, user)
    query = select(ExternalPracticeRecord).where(
        ExternalPracticeRecord.patient_id == patient_id,
        ExternalPracticeRecord.record_type == "TRAINING_PLAN")
    key_filter = None
    if snapshot_id:
        anchor = db.scalar(query.where(ExternalPracticeRecord.id == snapshot_id))
        if anchor is None:
            raise not_found("计划版本不存在。")
        key_filter, _ = _plan_preview(anchor, on_date)
        query = query.where(ExternalPracticeRecord.device_id == anchor.device_id)
    groups = defaultdict(list)
    for row in db.scalars(query.order_by(ExternalPracticeRecord.created_at.desc(),
                                          ExternalPracticeRecord.id.desc()).execution_options(yield_per=50)):
        key, preview = _plan_preview(row, on_date)
        if key_filter is None or key == key_filter:
            groups[key].append(preview)
    items = []
    for versions in groups.values():
        ordered = any(v["snapshot_revision"] is not None for v in versions)
        if ordered:
            versions.sort(key=lambda v: v["snapshot_revision"] if v["snapshot_revision"] is not None else -1, reverse=True)
        selected = versions if snapshot_id else versions[:1]
        items.extend({**v, "version_count": len(versions),
                      "version_order": "source_revision" if v["snapshot_revision"] is not None else "receipt"} for v in selected)
    page = items[offset:offset+limit]
    return {"items": page, "next_offset": offset+limit if offset+limit < len(items) else None}


@router.get("/records/{record_id}")
def record_detail(record_id: str, patient_id: str, db: DbSession, user: CurrentUser) -> dict:
    access.patient(db, patient_id,user)
    row = db.get(ExternalPracticeRecord, record_id)
    if row is None or row.patient_id != patient_id:
        raise not_found("记录不存在或不属于该患者。")
    return _record_out(row, include_payload=True)


@router.get("/capabilities")
def capabilities(user: CurrentUser, db: DbSession) -> dict:
    from app.ml.micro_expression.adapter import analyzer
    from app.api.face_recordings import available
    from app.api.integration_changes import supported
    state = analyzer.refresh_status()
    return {"sync_changes_ready": supported(db), "face_recordings_ready": available(), "face_recording_chunk_bytes": 4*1024*1024, "face_recording_max_bytes": 400*1024*1024, "face_recording_retention_days": 7, "face_model_ready": bool(state.is_ready),
            "face_model_state": str(state.state),
            "face_needs_keyframes": settings.micro_expression_entry == "causalnet",
            "ai_assistant_ready": True, "knowledge_ready": True, "ai_provider_ready": bool(settings.expert_llm_base_url and settings.expert_llm_model), "protocol_revision": "1.2" if available() else "1.1"}


def _face_out(job: MobileFaceJob) -> dict:
    return {"job_id": job.id, "status": job.status, "patient_id": job.patient_id,
            "result_id": job.result_id, "assessment_session_id": job.assessment_session_id,
            "error_code": job.error_code, "message": job.error_message,
            "created_at": job.created_at.isoformat()}


def _run_face(job_id: str):
    from app.services.integration_jobs import run_face
    return run_face(job_id)


def inspect_review_video(path):
    from app.ml.micro_expression.causalnet_preprocess import decode_video
    from app.jobs.gpu_inference import inference_manager
    with inference_manager.acquire_sync():return decode_video(path)


@router.post("/face/jobs", status_code=202)
async def submit_face_video(background: BackgroundTasks, db: DbSession, user: CurrentUser,
                            patient_id: str = Form(...), video: UploadFile = File(...),
                            device_id: str = Form(...), local_profile_id: str = Form(...)) -> dict:
    _bound(db, device_id, local_profile_id, patient_id,user)
    from app.ml.micro_expression.adapter import analyzer
    if not analyzer.refresh_status().is_ready:
        raise APIError(503, ErrorCode.MODEL_NOT_CONFIGURED, "面部分析服务尚未准备好。")
    extension = Path(video.filename or "").suffix.lower()
    if extension not in settings.allowed_video_suffixes:
        raise APIError(415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, "不支持该视频格式。")
    directory = settings.upload_path / "integration"
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{uuid.uuid4()}{extension}"
    limit_request(user,'upload',4)
    with _admission:
        count=db.scalar(select(func.count()).select_from(MobileFaceJob.__table__).where(MobileFaceJob.__table__.c.status.in_(['UPLOADING','REVIEW_REQUIRED','PENDING','RUNNING'])))
        if count>=8:raise APIError(429,'QUEUE_FULL','面部分析队列已满，请稍后重试。')
        job=MobileFaceJob(patient_id=patient_id,operator_id=user.id,device_id=device_id,local_profile_id=local_profile_id,
            stored_path=str(dest.relative_to(settings.upload_path)),source_filename=Path(video.filename or 'video').name[:200],status='UPLOADING',size_bytes=0)
        db.add(job);db.commit();db.refresh(job)
    size = 0
    try:
        with dest.open("xb") as target:
            os.chmod(dest, 0o600)
            while part := await video.read(1024 * 1024):
                size += len(part)
                if size > min(settings.max_upload_size_mb, 50) * 1024 * 1024:
                    raise APIError(413, ErrorCode.FILE_TOO_LARGE, "视频文件过大。")
                target.write(part)
        if not size:
            raise APIError(422, ErrorCode.VALIDATION_ERROR, "视频文件为空。")
    except BaseException:
        dest.unlink(missing_ok=True)
        db.rollback();job=db.get(MobileFaceJob,job.id)
        if job:job.status='FAILED';job.stored_path=None;job.error_code='UPLOAD_FAILED';db.commit()
        raise
    review = settings.micro_expression_entry == "causalnet"
    job.size_bytes=size
    job.status='REVIEW_REQUIRED' if review else 'PENDING'
    db.commit();db.refresh(job)
    return _face_out(job)


class FrameReview(BaseModel):
    onset_frame: int = Field(ge=1, le=1800)
    apex_frame: int = Field(ge=1, le=1800)
    offset_frame: int = Field(ge=1, le=1800)
    review_confirmed: bool = False


@router.post("/face/jobs/{job_id}/review", status_code=202)
def review_face_job(job_id: str, payload: FrameReview, background: BackgroundTasks,
                    db: DbSession, user: CurrentUser) -> dict:
    job = access.job(db,job_id,user)
    if job.status != "REVIEW_REQUIRED": raise conflict("当前任务无需或无法提交关键帧。")
    if not payload.review_confirmed:
        raise APIError(422, ErrorCode.VALIDATION_ERROR, "请先确认三个关键帧。")
    if not payload.onset_frame < payload.apex_frame < payload.offset_frame:
        raise APIError(422, ErrorCode.VALIDATION_ERROR, "帧位置应为起始帧 < 峰值帧 < 结束帧。")
    if not job.stored_path:raise not_found('视频已过期，请重新上传。')
    path=(settings.upload_path/job.stored_path).resolve()
    if not path.is_relative_to(settings.upload_path.resolve()) or not path.is_file():raise not_found('视频已过期，请重新上传。')
    from app.ml.micro_expression.causalnet_preprocess import VideoInputError
    try:info=inspect_review_video(path)
    except VideoInputError as exc:raise APIError(422,ErrorCode.VALIDATION_ERROR,str(exc)) from exc
    if payload.offset_frame>info['frame_count']:
        raise APIError(422,ErrorCode.VALIDATION_ERROR,'关键帧超过视频实际长度。')
    indices=[payload.onset_frame,payload.apex_frame,payload.offset_frame]
    changed=db.execute(update(MobileFaceJob).where(MobileFaceJob.id==job.id,MobileFaceJob.status=='REVIEW_REQUIRED').values(status='PENDING',indices_json=json.dumps(indices)))
    if changed.rowcount!=1:db.rollback();raise conflict('任务状态已变化，请刷新。')
    db.commit();db.refresh(job)
    return _face_out(job)


@router.get("/face/jobs/{job_id}")
def face_job_status(job_id: str, db: DbSession, user: CurrentUser) -> dict:
    job = access.job(db,job_id,user)
    result = _face_out(job)
    if job.status == "SUCCESS" and job.result_id:
        from app.db.models import MicroExpressionResult
        row = db.get(MicroExpressionResult, job.result_id)
        if row:
            result["result"] = {"model_name": row.model_name, "model_version": row.model_version,
              "predicted_class": row.predicted_class, "dominant_tag": row.dominant_tag,
              "tag_distribution": json.loads(row.tag_distribution_json) if row.tag_distribution_json else None,
              "inference_time_ms": row.inference_time_ms}
    return result


def cleanup_orphaned_face_jobs():
    from app.services.integration_jobs import recover_jobs
    recover_jobs()


class ExpertQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=3000)
    patient_id: str | None = None


def _ask_llm(system_prompt: str, question: str) -> str:
    """Minimal configurable OpenAI-compatible chat call. No patient records sent."""
    base = settings.expert_llm_base_url.rstrip("/")
    if not base or not settings.expert_llm_model :
        raise APIError(503, ErrorCode.MODEL_NOT_CONFIGURED, "AI 问答服务未配置。")
    from urllib.parse import urlparse
    urlparts=urlparse(base)
    local_ok=settings.expert_llm_allow_local_http and urlparts.scheme=='http' and urlparts.hostname in ('127.0.0.1','localhost','::1')
    if not base.startswith("https://") and not local_ok:
        raise APIError(503, ErrorCode.MODEL_UNAVAILABLE, "AI 服务地址必须使用 HTTPS。")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    body = json.dumps({"model": settings.expert_llm_model, "stream": False, "max_tokens": 512, "temperature": 0.2,
      "messages": [{"role":"system", "content": system_prompt},
          {"role":"user", "content": question}]}).encode("utf-8")
    request = UrlRequest(url, body, {"Content-Type":"application/json",
       "Authorization":"Bearer " + settings.expert_llm_api_key}, method="POST")
    try:
        with urlopen(request, timeout=settings.expert_llm_timeout_sec) as response:
            data = json.load(response)
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip(): raise ValueError("empty answer")
        return content.strip()
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, ValueError) as exc:
        raise APIError(502, ErrorCode.MODEL_UNAVAILABLE, "AI 问答暂时不可用。") from exc


@router.post("/expert/chat")
async def expert_chat(payload: ExpertQuestion, db: DbSession, user: CurrentUser) -> dict:
    if payload.patient_id:
        access.patient(db, payload.patient_id,user)
    limit_request(user,'chat',12)
    from app.services.integration_knowledge import answer_question
    response = await run_in_threadpool(answer_question,payload.question.strip(),_ask_llm)
    answer=response['answer']
    turn = ExpertChatTurn(operator_id=user.id, patient_id=payload.patient_id,
        question=payload.question.strip(), answer=answer, model=response["model"])
    db.add(turn); db.commit(); db.refresh(turn)
    return {**response,"id": turn.id, "answer": answer, "model": turn.model,
            "patient_data_used": False, "created_at": turn.created_at.isoformat()}

@router.get('/face/jobs/{job_id}/candidates')
async def face_review_candidates(job_id: str, db: DbSession, user: CurrentUser) -> dict:
    """Reviewed candidates, never auto-approve clinical frame boundaries."""
    from app.ml.micro_expression.adapter import analyzer
    job = access.job(db,job_id,user)
    if job.status != 'REVIEW_REQUIRED' or not job.stored_path:
        raise conflict("当前任务无需关键帧复核。")
    limit_request(user,'candidates',4)
    if job.candidates_json:return json.loads(job.candidates_json)
    path = (settings.upload_path / job.stored_path).resolve()
    if not path.is_relative_to(settings.upload_path.resolve()):raise not_found('视频已失效。')
    if not path.is_file(): raise not_found("视频已过期，请重新上传。")
    result=await run_in_threadpool(analyzer.spot,str(path))
    db.refresh(job)
    if job.status!='REVIEW_REQUIRED':raise conflict('任务状态已变化。')
    access.job(db,job.id,user)
    job.candidates_json=json.dumps(result,ensure_ascii=False);db.commit()
    return result

@router.get('/patient-data')
def patient_data(patient_id: str, db: DbSession, user: CurrentUser,
                 limit: int = Query(30, ge=1, le=100),
                 offset: int = Query(0, ge=0)) -> dict:
    """Authorized Web→Flutter snapshot, namespaced by original entity type.

    Flutter saves this to a separate cache. These records MUST NOT be inserted
    into its validated native practice.db tables: they use different formulas.
    """
    from app.db.models import (PianoSession, PoseSession, GuidedSongSession,
        TrainingPlan, FingerTappingResult, MicroExpressionResult,
        FunctionalAssessment)
    access.patient(db, patient_id,user)
    parent_ids = select(AssessmentSession.id).where(AssessmentSession.patient_id == patient_id)
    entities = {
        'assessment_sessions': (AssessmentSession, AssessmentSession.patient_id == patient_id),
        'piano_sessions': (PianoSession, PianoSession.patient_id == patient_id),
        'pose_sessions': (PoseSession, PoseSession.patient_id == patient_id),
        'guided_song_sessions': (GuidedSongSession, GuidedSongSession.patient_id == patient_id),
        'training_plans': (TrainingPlan, TrainingPlan.patient_id == patient_id),
        'micro_expression_results': (MicroExpressionResult, MicroExpressionResult.assessment_session_id.in_(parent_ids)),
        'finger_tapping_results': (FingerTappingResult, FingerTappingResult.assessment_session_id.in_(parent_ids)),
        'functional_assessments': (FunctionalAssessment, FunctionalAssessment.assessment_session_id.in_(parent_ids)),
        'external_practice_records': (ExternalPracticeRecord, ExternalPracticeRecord.patient_id == patient_id),
    }
    sensitive = {'password_hash','stored_path','raw_timeseries_path','original_filename'}
    output = {}
    more = False
    for key, (model, condition) in entities.items():
        rows = db.scalars(select(model).where(condition).order_by(model.id).offset(offset).limit(limit + 1)).all()
        if len(rows) > limit: more = True
        output[key] = []
        for row in rows[:limit]:
            item = {}
            for column in model.__table__.columns:
                if column.name in sensitive: continue
                value = getattr(row, column.name)
                if isinstance(value, (datetime,)): value = value.isoformat()
                item[column.name] = value
            output[key].append(item)
    return {'schema_version': '1.0', 'patient_id': patient_id,
            'categories': output, 'next_offset': offset + limit if more else None}


class AccessChange(BaseModel):
    active: bool

@router.put('/access/{patient_id}/{staff_id}')
def set_access(patient_id:str,staff_id:str,payload:AccessChange,db:DbSession,user:CurrentUser):
    from app.db.models import PatientAccessGrant
    from app.services import audit_service
    if user.role!='ADMIN':raise APIError(403,ErrorCode.FORBIDDEN,'只有管理员可以分配跨端患者权限。')
    _patient(db,patient_id)
    if db.get(StaffUser,staff_id) is None:raise not_found('工作人员不存在。')
    row=db.scalar(select(PatientAccessGrant).where(PatientAccessGrant.patient_id==patient_id,PatientAccessGrant.staff_user_id==staff_id))
    if row is None:row=PatientAccessGrant(patient_id=patient_id,staff_user_id=staff_id,active=payload.active);db.add(row)
    row.active=payload.active;db.commit()
    audit_service.record(db,staff_user_id=user.id,action='INTEGRATION_ACCESS_CHANGE',entity_type='patient',entity_id=patient_id,detail={'staff_id':staff_id,'active':payload.active})
    return {'patient_id':patient_id,'staff_id':staff_id,'active':row.active}

@router.delete('/bindings/{binding_id}')
def revoke_binding(binding_id:str,db:DbSession,user:CurrentUser):
    from app.services import audit_service
    link=db.get(DevicePatientLink,binding_id)
    if link is None:raise not_found('绑定不存在。')
    if link.bound_by!=user.id and user.role!='ADMIN':raise APIError(403,ErrorCode.FORBIDDEN,'无权撤销此绑定。')
    access.patient(db,link.patient_id,user)
    link.active=False;db.commit()
    audit_service.record(db,staff_user_id=user.id,action='INTEGRATION_BINDING_REVOKE',entity_type='device_patient_link',entity_id=link.id)
    return {'binding_id':link.id,'active':False}
