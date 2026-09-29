"""Pose training service.

The recording is analysed first and stored second, and the raw metrics are
written whether or not the quality gates accepted it. A refused recording keeps
its measurements so the operator can see what went wrong, but the session is
never sold as a valid result: `completed_at` is only set when the analysis was
accepted.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import APIError, ErrorCode, not_found
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import MediaFile, Patient, PoseSession
from app.ml.pose.analyzer import PoseOutcome, analyse, describe_thresholds
from app.ml.pose.exercises import (
    EXERCISE_DEFINITION_VERSION,
    EXERCISES,
    get_exercise,
    list_exercises,
)
from app.ml.pose.landmarks import PoseExtractionError, extract_landmarks
from app.db.enums import MediaType
from app.ml.pose.metrics import POSE_METRICS_ALGORITHM_VERSION
from app.schemas.pose import PoseSessionCreate

logger = get_logger(__name__)


def _dump(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _get_patient(db: Session, patient_id: str) -> Patient:
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted.is_(False))
    ).scalar_one_or_none()
    if patient is None:
        raise not_found("患者不存在或已被删除。", {"patient_id": patient_id})
    return patient


def create_session(db: Session, patient_id: str, payload: PoseSessionCreate) -> PoseSession:
    _get_patient(db, patient_id)
    session = PoseSession(
        patient_id=patient_id,
        exercise_type=payload.exercise_type,
        input_source=payload.input_source,
        difficulty_json=_dump(payload.difficulty),
        algorithm_version=POSE_METRICS_ALGORITHM_VERSION,
        exercise_definition_version=EXERCISE_DEFINITION_VERSION,
        started_at=utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> PoseSession:
    session = db.execute(
        select(PoseSession).where(PoseSession.id == session_id)
    ).scalar_one_or_none()
    if session is None:
        raise not_found("动作训练会话不存在。", {"session_id": session_id})
    return session


def list_sessions(
    db: Session, patient_id: str, *, page: int = 1, page_size: int = 20
) -> tuple[list[PoseSession], int]:
    total = db.execute(
        select(func.count())
        .select_from(PoseSession)
        .where(PoseSession.patient_id == patient_id)
    ).scalar_one()
    stmt = (
        select(PoseSession)
        .where(PoseSession.patient_id == patient_id)
        .order_by(PoseSession.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.execute(stmt).scalars().all()), int(total)


def write_outcome(db: Session, session: PoseSession, outcome: PoseOutcome) -> PoseSession:
    """Store an analysis result, accepted or not."""
    session.raw_metrics_json = _dump(outcome.metrics)
    session.quality_json = _dump(outcome.quality)
    session.algorithm_version = outcome.algorithm_version
    session.exercise_definition_version = EXERCISE_DEFINITION_VERSION

    metrics = outcome.metrics
    session.hold_time_sec = metrics.get("hold_time_sec")
    session.repetition_count = metrics.get("repetition_count")
    session.movement_speed = metrics.get("movement_speed_deg_per_sec")
    session.valid_pose_frame_ratio = metrics.get("valid_pose_frame_ratio")

    # Display scores stay NULL. There is no formula to compute them from, and
    # writing a plausible number here would be inventing a clinical result.
    session.completion_score = None
    session.range_of_motion = None
    session.symmetry_score = None
    session.stability_score = None

    session.completed_at = utcnow() if outcome.accepted else None
    db.commit()
    db.refresh(session)
    return session


def _model_path() -> Path:
    """Where the pose landmarker lives.

    A function rather than a direct settings read so a test can substitute a
    stub: the landmarker's own behaviour is verified against real input, not in
    the unit tests, and those tests must not depend on a 5 MB download.
    """
    return settings.pose_landmarker_model_path


def analyse_recording(
    db: Session,
    session_id: str,
    video_path: str | Path,
    *,
    media_file_id: str | None = None,
) -> tuple[PoseSession, PoseOutcome]:
    """Run the pose pipeline for one session and store what it produced."""
    session = get_session(db, session_id)
    exercise = get_exercise(session.exercise_type)
    if exercise is None:
        raise not_found(
            "未知的动作类型。", {"exercise_type": session.exercise_type}
        )

    model_path = _model_path()
    if not model_path.is_file():
        raise APIError(
            503,
            ErrorCode.MODEL_NOT_CONFIGURED,
            "未配置 MediaPipe Pose Landmarker 模型文件，无法进行动作分析。",
            {"expected_path": str(model_path)},
        )

    try:
        series = extract_landmarks(
            video_path,
            model_path=model_path,
            frame_stride=settings.pose_frame_stride,
            max_frames=settings.pose_max_frames,
        )
    except PoseExtractionError as exc:
        raise APIError(
            422,
            ErrorCode.VIDEO_UNREADABLE,
            str(exc),
            {"video": str(video_path)},
        ) from exc

    outcome = analyse(series, session.exercise_type)

    if media_file_id is not None:
        session.media_file_id = media_file_id

    write_outcome(db, session, outcome)
    logger.info(
        "pose session %s: exercise=%s accepted=%s gates=%s reps=%s",
        session_id[:8],
        session.exercise_type,
        outcome.accepted,
        outcome.gate_failures,
        outcome.metrics.get("repetition_count"),
    )
    return session, outcome


def analyze_pose_video(
    db: Session,
    session_id: str,
    *,
    patient_id: str,
    original_filename: str | None,
    content: bytes,
    mime_type: str | None = None,
) -> tuple[PoseSession, PoseOutcome, MediaFile]:
    """Store an uploaded recording and analyse it.

    The file is written first so a failed analysis still leaves the recording
    available for a retry, and a MediaFile row is created so the number and the
    video stay linked.
    """
    from app.services.assessment_service import store_upload

    path, sha256, relative = store_upload(
        patient_id=patient_id,
        original_filename=original_filename,
        content=content,
        media_type=MediaType.POSE_VIDEO,
    )

    media = MediaFile(
        patient_id=patient_id,
        type="POSE_VIDEO",
        original_filename=original_filename,
        stored_path=relative,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=sha256,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    session, outcome = analyse_recording(
        db, session_id, path, media_file_id=media.id
    )
    return session, outcome, media


def exercises_payload() -> list[dict]:
    out: list[dict] = []
    for exercise in list_exercises():
        out.append(
            {
                "key": exercise["key"],
                "name_zh": exercise["name_zh"],
                "description": exercise["description"],
                "joints": exercise["joints"],
                "raw_metrics": exercise["raw_metrics"],
                "hold_time_sec": exercise["hold_time_sec"],
                "target_repetitions": exercise["target_repetitions"],
                "contraindications": exercise["contraindications"],
                "scores_available": exercise["scores_available"],
                "score_formulas": {
                    "completion": exercise["completion_formula"],
                    "rom": exercise["rom_formula"],
                    "symmetry": exercise["symmetry_formula"],
                    "stability": exercise["stability_formula"],
                },
            }
        )
    return out


def thresholds_payload() -> dict:
    return describe_thresholds()


def exercises_defined() -> int:
    return len(EXERCISES)
