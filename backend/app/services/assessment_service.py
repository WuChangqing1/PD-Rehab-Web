"""Assessment session service.

A session is the shared time anchor for micro-expression, finger tapping (left
and right) and optional functional tests, so results recorded at different
moments can never be merged into one assessment by accident.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, settings
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.db.base import utcnow
from app.db.enums import (
    AssessmentSessionType,
    Hand,
    JobType,
    MediaType,
    SessionStatus,
)
from app.db.models import (
    AssessmentSession,
    FingerTappingResult,
    MicroExpressionResult,
    Patient,
)
from app.jobs.manager import job_manager
from app.ml.micro_expression.adapter import analyzer as micro_expression_analyzer
from app.schemas.assessment import (
    AssessmentSessionCreate,
    AssessmentSessionUpdate,
    FingerTappingAnalyzeRequest,
    LeftRightComparison,
    MicroExpressionAnalyzeRequest,
)

# Metrics compared between hands (spec V2 section 13).
_COMPARISON_METRICS = (
    "avg_amplitude",
    "avg_speed",
    "tapping_frequency",
    "cycle_cv",
)


# ------------------------------------------------------------------- sessions
def create_session(
    db: Session,
    patient_id: str,
    payload: AssessmentSessionCreate,
    *,
    created_by: str | None = None,
) -> AssessmentSession:
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted.is_(False))
    ).scalar_one_or_none()
    if patient is None:
        raise not_found("患者不存在或已被删除。", {"patient_id": patient_id})

    medication_state = payload.medication_state
    if medication_state == "UNKNOWN" and patient.medication_state:
        medication_state = patient.medication_state

    session = AssessmentSession(
        patient_id=patient_id,
        session_type=str(payload.session_type),
        medication_state=str(medication_state),
        status=str(SessionStatus.IN_PROGRESS),
        created_by=created_by,
        started_at=utcnow(),
        notes=payload.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> AssessmentSession:
    session = db.execute(
        select(AssessmentSession).where(AssessmentSession.id == session_id)
    ).scalar_one_or_none()
    if session is None:
        raise not_found("评估会话不存在。", {"session_id": session_id})
    return session


def list_sessions(
    db: Session, patient_id: str, *, page: int = 1, page_size: int = 20
) -> tuple[list[AssessmentSession], int]:
    count_stmt = (
        select(func.count())
        .select_from(AssessmentSession)
        .where(AssessmentSession.patient_id == patient_id)
    )
    total = db.execute(count_stmt).scalar_one()
    stmt = (
        select(AssessmentSession)
        .where(AssessmentSession.patient_id == patient_id)
        .order_by(AssessmentSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.execute(stmt).scalars().all()), total


def update_session(
    db: Session, session_id: str, payload: AssessmentSessionUpdate
) -> AssessmentSession:
    session = get_session(db, session_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(session, key, str(value) if value is not None else None)
    db.commit()
    db.refresh(session)
    return session


def complete_session(db: Session, session_id: str, notes: str | None = None) -> AssessmentSession:
    session = get_session(db, session_id)
    if session.status == str(SessionStatus.COMPLETED):
        raise conflict("该评估会话已完成。", {"session_id": session_id})
    session.status = str(SessionStatus.COMPLETED)
    session.completed_at = utcnow()
    if notes is not None:
        session.notes = notes
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------- media
def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def store_upload(
    *,
    patient_id: str,
    original_filename: str | None,
    content: bytes,
    media_type: MediaType,
) -> tuple[Path, str, str]:
    """Persist an upload under a UUID name.

    Real filenames never contain patient names or identifiers
    (spec V2 section 51). Returns (path, sha256, stored_relative_path).
    """
    suffix = Path(original_filename or "").suffix.lower()
    allowed = settings.allowed_video_suffixes
    if media_type is not MediaType.REPORT and suffix not in allowed:
        raise APIError(
            415,
            ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            f"不支持的文件类型 {suffix or '(无扩展名)'}，仅支持 {sorted(allowed)}。",
            {"filename": original_filename},
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise APIError(
            413,
            ErrorCode.FILE_TOO_LARGE,
            f"文件超过大小上限 {settings.max_upload_size_mb} MB。",
            {"size_bytes": len(content), "max_bytes": max_bytes},
        )

    day = date.today().isoformat()
    target_dir = settings.upload_path / patient_id / day
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4()}{suffix or '.bin'}"
    target = target_dir / stored_name
    target.write_bytes(content)

    relative = target.relative_to(PROJECT_ROOT).as_posix()
    return target, _sha256_of(target), relative


# --------------------------------------------------------- micro expression
def analyze_micro_expression(
    db: Session,
    session_id: str,
    *,
    patient_id: str,
    original_filename: str | None,
    content: bytes,
    payload: MicroExpressionAnalyzeRequest,
    created_by: str | None = None,
):
    """Upload a video and run the real model through the adapter.

    If the model is not configured the adapter raises MODEL_NOT_CONFIGURED and
    nothing is written. No mock result is ever produced.
    """
    session = get_session(db, session_id)
    _assert_session_accepts(session)

    path, sha256, relative = store_upload(
        patient_id=patient_id,
        original_filename=original_filename,
        content=content,
        media_type=MediaType.MICRO_EXPRESSION_VIDEO,
    )

    from app.db.models import MediaFile  # local import keeps the module graph flat

    media = MediaFile(
        patient_id=patient_id,
        assessment_session_id=session_id,
        type=str(MediaType.MICRO_EXPRESSION_VIDEO),
        original_filename=original_filename,
        stored_path=relative,
        mime_type=_mime_for(path.suffix),
        size_bytes=len(content),
        sha256=sha256,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    # Raises MODEL_NOT_CONFIGURED / MODEL_UNAVAILABLE while no real model exists.
    result = micro_expression_analyzer.analyze(str(path))

    row = MicroExpressionResult(
        assessment_session_id=session_id,
        media_file_id=media.id,
        model_name=result.get("model_name"),
        model_version=result.get("model_version"),
        feature_schema_version=result.get("feature_schema_version") or "1.0",
        predicted_class=result.get("predicted_class"),
        pd_probability=result.get("pd_probability"),
        dominant_tag=result.get("dominant_tag"),
        tag_distribution_json=_dump(result.get("tag_distribution")),
        raw_output_json=_dump(result.get("raw_output_json")),
        inference_time_ms=result.get("inference_time_ms"),
        quality_json=_dump(result.get("quality_json")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, media


def list_micro_expression(db: Session, session_id: str) -> list[MicroExpressionResult]:
    stmt = (
        select(MicroExpressionResult)
        .where(MicroExpressionResult.assessment_session_id == session_id)
        .order_by(MicroExpressionResult.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


# ----------------------------------------------------------- finger tapping
def analyze_finger_tapping(
    db: Session,
    session_id: str,
    *,
    patient_id: str,
    original_filename: str | None,
    content: bytes,
    payload: FingerTappingAnalyzeRequest,
    created_by: str | None = None,
):
    """Upload a finger tapping video and analyse one hand.

    Phase 1: the pipeline is not implemented (Phase 4), so this returns a job
    that fails with NOT_IMPLEMENTED rather than inventing metrics.
    """
    session = get_session(db, session_id)
    _assert_session_accepts(session)

    path, sha256, relative = store_upload(
        patient_id=patient_id,
        original_filename=original_filename,
        content=content,
        media_type=MediaType.FINGER_TAPPING_VIDEO,
    )

    from app.db.models import MediaFile

    media = MediaFile(
        patient_id=patient_id,
        assessment_session_id=session_id,
        type=str(MediaType.FINGER_TAPPING_VIDEO),
        original_filename=original_filename,
        stored_path=relative,
        mime_type=_mime_for(path.suffix),
        size_bytes=len(content),
        sha256=sha256,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    def _run():
        from app.ml.finger_tapping.pipeline import analyze_video  # Phase 4

        return analyze_video(str(path), str(payload.hand))

    job = job_manager.run_sync(JobType.FINGER_TAPPING_ANALYSIS, _run)
    return job, media


def list_finger_tapping(db: Session, session_id: str) -> list[FingerTappingResult]:
    stmt = (
        select(FingerTappingResult)
        .where(FingerTappingResult.assessment_session_id == session_id)
        .order_by(FingerTappingResult.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def compare_left_right(results: list[FingerTappingResult]) -> list[LeftRightComparison]:
    """Left/right summary for a session.

    absolute_difference = left - right, as required by spec V2 section 13.
    A missing side yields None; it is never replaced by 0.
    """
    by_hand: dict[str, FingerTappingResult] = {}
    for row in results:
        # newest wins if a hand was analysed more than once
        current = by_hand.get(row.hand)
        if current is None or row.created_at >= current.created_at:
            by_hand[row.hand] = row

    left = by_hand.get(str(Hand.LEFT))
    right = by_hand.get(str(Hand.RIGHT))

    comparisons: list[LeftRightComparison] = []
    for metric in _COMPARISON_METRICS:
        lv = getattr(left, metric, None) if left else None
        rv = getattr(right, metric, None) if right else None
        difference = None
        ratio = None
        if lv is not None and rv is not None:
            difference = lv - rv
            denom = (lv + rv) / 2
            ratio = (lv - rv) / denom if abs(denom) > 1e-9 else None
        comparisons.append(
            LeftRightComparison(
                metric=metric,
                left=lv,
                right=rv,
                absolute_difference=difference,
                asymmetry_ratio=ratio,
            )
        )
    return comparisons


# -------------------------------------------------------------------- helpers
def _assert_session_accepts(session: AssessmentSession) -> None:
    if session.status == str(SessionStatus.COMPLETED):
        raise conflict("该评估会话已完成，无法继续添加结果。", {"session_id": session.id})
    if session.status == str(SessionStatus.ABORTED):
        raise conflict("该评估会话已中止，无法继续添加结果。", {"session_id": session.id})


def _dump(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _mime_for(suffix: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
    }.get(suffix.lower(), "application/octet-stream")


def session_type_matches(session: AssessmentSession, expected: AssessmentSessionType) -> bool:
    return session.session_type in (str(expected), str(AssessmentSessionType.COMPREHENSIVE))
