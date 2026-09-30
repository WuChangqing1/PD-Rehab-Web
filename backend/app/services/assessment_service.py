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
from app.core.logging import get_logger
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

logger = get_logger(__name__)

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
    db: Session,
    patient_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> tuple[list[AssessmentSession], int]:
    """Sessions for one patient, newest first.

    `status` exists so the assessment centre can list the unfinished sessions a
    patient already has instead of silently picking one: a doctor must be told
    that a previous assessment is still open and choose what to do with it.
    """
    conditions = [AssessmentSession.patient_id == patient_id]
    if status:
        conditions.append(AssessmentSession.status == status)

    total = db.execute(
        select(func.count()).select_from(AssessmentSession).where(*conditions)
    ).scalar_one()
    stmt = (
        select(AssessmentSession)
        .where(*conditions)
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
    """Close a session, but only when it actually has the work it claims.

    Until this was enforced any session could be marked complete regardless of
    what had been collected, so the summary page could report "综合评估已完成"
    for a session with no results at all. What counts as complete depends on the
    session type and on which modules are available -- an unavailable model is
    not a reason to pretend it ran.
    """
    session = get_session(db, session_id)
    if session.status == str(SessionStatus.COMPLETED):
        raise conflict("该评估会话已完成。", {"session_id": session_id})

    readiness = completion_readiness(db, session)
    if not readiness["can_complete"]:
        raise conflict(
            "本次评估尚未完成必填项目，无法标记完成。",
            {"session_id": session_id, "items": readiness["items"]},
        )

    session.status = str(SessionStatus.COMPLETED)
    session.completed_at = utcnow()
    if notes is not None:
        session.notes = notes
    # Record which modules were skipped and why, so a later reader cannot mistake
    # an unavailable model for a completed one.
    skipped = [i for i in readiness["items"] if i["state"] == "SKIPPED_MODEL_UNAVAILABLE"]
    if skipped:
        session.notes = (session.notes or "") + (
            "\n[SKIPPED_MODEL_UNAVAILABLE] "
            + "、".join(i["label"] for i in skipped)
        )
    db.commit()
    db.refresh(session)
    return session


def completion_readiness(db: Session, session: AssessmentSession) -> dict:
    """What still has to happen before this session may be completed.

    Deliberately derived from stored results, not from a counter the client
    sends: the check has to hold however the results arrived.
    """
    results = list_finger_tapping(db, session.id)
    hands = {str(r.hand) for r in results}
    micro = list_micro_expression(db, session.id)

    from app.ml.registry import registry

    status = registry.get("micro_expression_model")
    micro_ready = bool(status is not None and status.is_ready)

    session_type = session.session_type
    items: list[dict] = []

    wants_micro = session_type in (
        str(AssessmentSessionType.COMPREHENSIVE),
        str(AssessmentSessionType.MICRO_EXPRESSION_ONLY),
    )
    wants_finger = session_type in (
        str(AssessmentSessionType.COMPREHENSIVE),
        str(AssessmentSessionType.FINGER_TAPPING_ONLY),
    )

    if wants_micro:
        if micro:
            state = "COMPLETED"
        elif micro_ready:
            state = "PENDING"
        else:
            # Not available is not the patient's fault and must not block the
            # assessment, but it is recorded as skipped rather than completed.
            state = "SKIPPED_MODEL_UNAVAILABLE"
        items.append({"key": "micro_expression", "label": "面部分析", "state": state})

    if wants_finger:
        for hand, label in (("LEFT", "左手手指敲击"), ("RIGHT", "右手手指敲击")):
            items.append(
                {
                    "key": f"finger_tapping_{hand.lower()}",
                    "label": label,
                    "state": "COMPLETED" if hand in hands else "PENDING",
                }
            )

    can_complete = all(item["state"] != "PENDING" for item in items)
    return {
        "session_type": session_type,
        "micro_expression_model_ready": micro_ready,
        "items": items,
        "can_complete": can_complete,
    }


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
    (spec V2 section 51). Returns (path, sha256, stored_path).

    `stored_path` is stored relative to the project root when the upload
    directory lives inside the project (local development). On a server the
    upload directory is deliberately outside the code tree -- it must not be
    wiped by a redeploy -- so an absolute path is stored instead. Deriving that
    with a bare relative_to() would raise ValueError and surface as an opaque
    500, so the fallback is explicit.
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
    target = (target_dir / stored_name).resolve()
    target.write_bytes(content)

    try:
        stored_path = target.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        # Upload directory is outside the project (typical on a server).
        stored_path = target.as_posix()

    return target, _sha256_of(target), stored_path


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
    _assert_session_accepts(session, AssessmentSessionType.MICRO_EXPRESSION_ONLY)

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

    The upload is always stored first so the record of the attempt survives even
    when the recording is rejected by quality control. A result row is written
    only when the pipeline actually produced features.

    `severity_score` / `severity_label` are left NULL: the upstream repository
    ships no trained severity model and no inference entry point, so any value
    here would be invented.
    """
    session = get_session(db, session_id)
    _assert_session_accepts(session, AssessmentSessionType.FINGER_TAPPING_ONLY)

    hand = str(payload.hand)
    path, sha256, stored_path = store_upload(
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
        stored_path=stored_path,
        mime_type=_mime_for(path.suffix),
        size_bytes=len(content),
        sha256=sha256,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    # Imported here so the module stays importable without opencv/mediapipe.
    from app.ml.finger_tapping.pipeline import analyze_video

    def _run() -> dict:
        return {"outcome": analyze_video(str(path), hand)}

    job = job_manager.run_sync(JobType.FINGER_TAPPING_ANALYSIS, _run)
    if job.status == "FAILED":
        return job, media, None

    outcome = (job.result_ref or {}).get("outcome")
    if outcome is None:  # pragma: no cover - defensive
        return job, media, None

    row = FingerTappingResult(
        assessment_session_id=session_id,
        media_file_id=media.id,
        hand=hand,
        **outcome.features,
        valid_frame_ratio=outcome.quality.get("valid_frame_ratio"),
        # The Tasks API exposes no per-landmark confidence (visibility and
        # presence are None). This holds the handedness classification score,
        # whose meaning is stated in quality_json.
        avg_landmark_confidence=outcome.quality.get("avg_landmark_confidence"),
        severity_score=outcome.severity_score,
        severity_label=outcome.severity_label,
        analyzer_version=outcome.analyzer_version,
        feature_schema_version=outcome.feature_schema_version,
        analysis_config_json=_dump(outcome.analysis_config),
        quality_json=_dump(outcome.quality),
        raw_features_json=_dump(outcome.raw_features),
        raw_timeseries_path=_write_timeseries(session_id, hand, outcome.timeseries),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # The job result references the persisted row rather than a raw payload.
    job.result_ref = {
        "finger_tapping_result_id": row.id,
        "hand": hand,
        "media_file_id": media.id,
    }
    return job, media, row


def _write_timeseries(session_id: str, hand: str, timeseries: dict) -> str | None:
    """Persist the aperture series next to the other outputs.

    Kept as .npz so reviewers can re-plot or re-threshold an analysis without
    re-running inference. Returns None when there is nothing to write.
    """
    if not timeseries or not timeseries.get("aperture_filtered"):
        return None
    try:
        import numpy as np

        target_dir = settings.output_path / session_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"finger_tapping_{hand.lower()}_timeseries.npz"
        np.savez_compressed(
            target,
            **{key: np.asarray(values) for key, values in timeseries.items()},
        )
        return target.as_posix()
    except Exception as exc:  # noqa: BLE001 - never fail an analysis over this
        logger.warning("could not write timeseries: %s: %s", type(exc).__name__, exc)
        return None


def list_finger_tapping(db: Session, session_id: str) -> list[FingerTappingResult]:
    stmt = (
        select(FingerTappingResult)
        .where(FingerTappingResult.assessment_session_id == session_id)
        .order_by(FingerTappingResult.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def load_timeseries(result: FingerTappingResult) -> dict[str, list[float]] | None:
    """Read the stored aperture series for one result.

    The series is what the features were computed from, so it is served
    unchanged. Returns None when nothing was persisted (for example a rejected
    recording) rather than fabricating a series.
    """
    path = result.raw_timeseries_path
    if not path:
        return None
    target = Path(path)
    if not target.is_file():
        logger.warning("timeseries file missing on disk: %s", path)
        return None
    try:
        import numpy as np

        with np.load(target) as data:
            return {key: [float(v) for v in data[key]] for key in data.files}
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not read timeseries %s: %s: %s", path, type(exc).__name__, exc)
        return None


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
def _assert_session_accepts(
    session: AssessmentSession, module: AssessmentSessionType | None = None
) -> None:
    """Reject results the session is not collecting.

    Status alone was not enough: a MICRO_EXPRESSION_ONLY session accepted finger
    tapping and a FINGER_TAPPING_ONLY session accepted video, so the stored data
    could contradict the session type the report is built from.
    """
    if session.status == str(SessionStatus.COMPLETED):
        raise conflict("该评估会话已完成，无法继续添加结果。", {"session_id": session.id})
    if session.status == str(SessionStatus.ABORTED):
        raise conflict("该评估会话已中止，无法继续添加结果。", {"session_id": session.id})

    if module is None:
        return

    if not session_type_matches(session, module):
        allowed = {
            str(AssessmentSessionType.COMPREHENSIVE): "综合评估（面部分析 + 左右手手指敲击）",
            str(AssessmentSessionType.MICRO_EXPRESSION_ONLY): "仅面部分析",
            str(AssessmentSessionType.FINGER_TAPPING_ONLY): "仅手指敲击",
            str(AssessmentSessionType.FUNCTIONAL_TEST): "功能测试（不使用本接口）",
        }.get(session.session_type, session.session_type)
        raise conflict(
            f"该评估会话的类型是「{allowed}」，不能记录其他类型的结果。",
            {
                "session_id": session.id,
                "session_type": session.session_type,
                "attempted": str(module),
            },
        )


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
    """Whether a session of this type collects the given module.

    A COMPREHENSIVE session collects everything; a single-module session collects
    only its own module. FUNCTIONAL_TEST is not an assessment container at all --
    functional tests live in the functional_assessments table.
    """
    if session.session_type == str(AssessmentSessionType.COMPREHENSIVE):
        return expected in (
            AssessmentSessionType.MICRO_EXPRESSION_ONLY,
            AssessmentSessionType.FINGER_TAPPING_ONLY,
        )
    return session.session_type == str(expected)
