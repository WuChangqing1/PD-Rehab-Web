"""Piano training service.

Raw events are persisted before any metric is considered, so the summary can
always be recomputed. Metrics are computed here (authoritative) and the client's
copy is stored alongside for comparison; a divergence between the two means one
implementation drifted, which would otherwise silently corrupt a trend line.
"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import conflict, not_found
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Baseline, Patient, PianoEvent, PianoSession
from app.schemas.piano import (
    PianoCompleteRequest,
    PianoEventsBatch,
    PianoSessionCreate,
)
from app.utils.piano_metrics import compute_metrics, validation_warnings

logger = get_logger(__name__)

CALIBRATION_MODE = "CALIBRATION"

# The eight calibration values required by spec V2 section 20.
_BASELINE_FIELDS = (
    "baseline_accuracy",
    "baseline_response_latency",
    "baseline_response_latency_cv",
    "baseline_timing_mae",
    "baseline_left_accuracy",
    "baseline_right_accuracy",
    "baseline_left_latency",
    "baseline_right_latency",
)


def _dump(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _load(text: str | None):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _get_patient(db: Session, patient_id: str) -> Patient:
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted.is_(False))
    ).scalar_one_or_none()
    if patient is None:
        raise not_found("患者不存在或已被删除。", {"patient_id": patient_id})
    return patient


def create_session(
    db: Session, patient_id: str, payload: PianoSessionCreate
) -> PianoSession:
    """Open a round and record the difficulty that will be used."""
    _get_patient(db, patient_id)
    config = payload.difficulty.model_dump()

    session = PianoSession(
        patient_id=patient_id,
        training_plan_id=payload.training_plan_id,
        mode=payload.mode,
        round_number=payload.round_number,
        input_source=payload.input_source,
        bpm=config["bpm"],
        judgement_window_ms=config["judgement_window_ms"],
        sequence_length=config["sequence_length"],
        note_density=config["note_density"],
        hand_mode=config["hand_mode"],
        weak_side_ratio=config["weak_side_ratio"],
        finger_complexity=config["finger_complexity"],
        session_duration_sec=config["session_duration_sec"],
        difficulty_before_json=_dump(
            {
                **config,
                "seed": payload.seed,
                "weak_hand": payload.weak_hand,
                "mode": payload.mode,
                "round_number": payload.round_number,
                "input_source": payload.input_source,
            }
        ),
        difficulty_engine_version=settings.piano_difficulty_version,
        metrics_version=settings.piano_metrics_version,
        started_at=utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> PianoSession:
    session = db.execute(
        select(PianoSession).where(PianoSession.id == session_id)
    ).scalar_one_or_none()
    if session is None:
        raise not_found("钢琴训练会话不存在。", {"session_id": session_id})
    return session


def store_events(
    db: Session, session_id: str, payload: PianoEventsBatch
) -> tuple[int, list[dict]]:
    """Persist raw events. Returns (stored count, event dicts).

    Events are written first and metrics only afterwards, so an interrupted
    upload still leaves the raw record intact.
    """
    session = get_session(db, session_id)
    if session.completed_at is not None:
        raise conflict(
            "该训练会话已完成，无法再追加事件。", {"session_id": session_id}
        )

    rows: list[PianoEvent] = []
    plain: list[dict] = []
    for event in payload.events:
        data = event.model_dump()
        rows.append(
            PianoEvent(
                session_id=session_id,
                event_index=data["event_index"],
                cue_onset_time_ms=data["cue_onset_time_ms"],
                target_time_ms=data["target_time_ms"],
                actual_time_ms=data["actual_time_ms"],
                response_latency_ms=data["response_latency_ms"],
                timing_error_ms=data["timing_error_ms"],
                key_code=data["key_code"],
                note=data["note"],
                hand=data["hand"],
                finger_hint=data["finger_hint"],
                key_down_time_ms=data["key_down_time_ms"],
                key_up_time_ms=data["key_up_time_ms"],
                hold_duration_ms=data["hold_duration_ms"],
                is_correct=data["is_correct"],
                is_missed=data["is_missed"],
            )
        )
        plain.append(data)

    db.add_all(rows)

    # Extra fields live in the difficulty audit column rather than new DB
    # columns, so no migration is needed for them.
    existing = _load(session.difficulty_before_json) or {}
    existing["events_meta"] = {
        "planned_cues": payload.planned_cues,
        "client_metrics": payload.client_metrics,
        "input_latency_note": payload.input_latency_note,
        "extra_event_fields": [
            "is_wrong_key",
            "cue_index",
            "sequence_position",
            "sequence_length",
        ],
    }
    existing["events_extra_json"] = _dump(
        [
            {
                "event_index": e["event_index"],
                "is_wrong_key": e["is_wrong_key"],
                "cue_index": e["cue_index"],
                "sequence_position": e["sequence_position"],
                "sequence_length": e["sequence_length"],
            }
            for e in plain
        ]
    )
    session.difficulty_before_json = _dump(existing)

    db.commit()
    logger.info("piano session %s: stored %d raw events", session_id[:8], len(rows))
    return len(rows), plain


def list_events(db: Session, session_id: str) -> list[PianoEvent]:
    stmt = (
        select(PianoEvent)
        .where(PianoEvent.session_id == session_id)
        .order_by(PianoEvent.event_index)
    )
    return list(db.execute(stmt).scalars().all())


def _event_dicts(db: Session, session: PianoSession) -> list[dict]:
    """Raw events as dicts, re-joined with the extra fields stored alongside."""
    rows = list_events(db, session.id)
    meta = _load(session.difficulty_before_json) or {}
    extras_raw = meta.get("events_extra_json")
    extras: dict[int, dict] = {}
    if extras_raw:
        try:
            for item in json.loads(extras_raw):
                extras[int(item["event_index"])] = item
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            extras = {}

    out: list[dict] = []
    for row in rows:
        event = {
            "event_index": row.event_index,
            "cue_onset_time_ms": row.cue_onset_time_ms,
            "target_time_ms": row.target_time_ms,
            "actual_time_ms": row.actual_time_ms,
            "response_latency_ms": row.response_latency_ms,
            "timing_error_ms": row.timing_error_ms,
            "key_code": row.key_code,
            "note": row.note,
            "hand": row.hand,
            "finger_hint": row.finger_hint,
            "key_down_time_ms": row.key_down_time_ms,
            "key_up_time_ms": row.key_up_time_ms,
            "hold_duration_ms": row.hold_duration_ms,
            "is_correct": row.is_correct,
            "is_missed": row.is_missed,
        }
        extra = extras.get(row.event_index, {})
        event["is_wrong_key"] = bool(extra.get("is_wrong_key", False))
        event["cue_index"] = extra.get("cue_index")
        event["sequence_position"] = extra.get("sequence_position")
        event["sequence_length"] = extra.get("sequence_length")
        out.append(event)
    return out


def event_dicts(db: Session, session: PianoSession) -> list[dict]:
    """Public accessor: the same joined view used for metric computation."""
    return _event_dicts(db, session)


def complete_session(
    db: Session, session_id: str, payload: PianoCompleteRequest
) -> tuple[PianoSession, dict]:
    """Recompute metrics from stored raw events and close the round."""
    session = get_session(db, session_id)
    if session.completed_at is not None:
        raise conflict("该训练会话已完成。", {"session_id": session_id})

    events = _event_dicts(db, session)
    meta = (_load(session.difficulty_before_json) or {}).get("events_meta") or {}
    planned = meta.get("planned_cues")

    metrics = compute_metrics(events, planned_cues=planned)
    warnings = validation_warnings(metrics, events)

    # Compare with what the client reported. A divergence means one of the two
    # implementations drifted and is worth surfacing rather than hiding.
    client = meta.get("client_metrics") or {}
    divergences: list[str] = []
    if client:
        for key, value in metrics.to_db_fields().items():
            if key not in client or client[key] is None or value is None:
                continue
            try:
                if abs(float(client[key]) - float(value)) > 1e-6:
                    divergences.append(f"{key}: client={client[key]} server={value}")
            except (TypeError, ValueError):
                continue
    if divergences:
        warnings.append("前端与后端指标不一致：" + "; ".join(divergences[:8]))

    for field_name, value in metrics.to_db_fields().items():
        setattr(session, field_name, value)

    if payload.difficulty_after is not None:
        session.difficulty_after_json = _dump(payload.difficulty_after.model_dump())
    if payload.adaptation is not None:
        session.adaptation_reason_json = _dump(payload.adaptation)

    # Keep the recomputed metric set and quality warnings with the session.
    audit = _load(session.difficulty_before_json) or {}
    audit["server_metrics"] = metrics.to_dict()
    audit["validation_warnings"] = warnings
    session.difficulty_before_json = _dump(audit)

    session.metrics_version = payload.metrics_version or settings.piano_metrics_version
    session.completed_at = utcnow()
    db.commit()
    db.refresh(session)

    logger.info(
        "piano session %s completed: mode=%s cues=%d accuracy=%s",
        session_id[:8],
        session.mode,
        metrics.total_cues,
        metrics.accuracy,
    )
    return session, {"metrics": metrics.to_dict(), "warnings": warnings}


def save_calibration_baseline(db: Session, session: PianoSession) -> Baseline:
    """Store a calibration round as the patient's active baseline.

    A new baseline deactivates the previous one but never deletes it
    (spec V2 section 33).
    """
    if session.mode != CALIBRATION_MODE:
        raise conflict(
            "只有 Calibration 会话可以建立基线。", {"mode": session.mode}
        )
    if session.completed_at is None:
        raise conflict("Calibration 会话尚未完成，无法建立基线。", {"session_id": session.id})

    audit = _load(session.difficulty_before_json) or {}
    server_metrics = audit.get("server_metrics") or {}

    snapshot = {
        "baseline_accuracy": session.accuracy,
        "baseline_response_latency": session.mean_response_latency_ms,
        "baseline_response_latency_cv": session.response_latency_cv,
        "baseline_timing_mae": session.timing_mae_ms,
        "baseline_left_accuracy": session.left_accuracy,
        "baseline_right_accuracy": session.right_accuracy,
        "baseline_left_latency": session.left_mean_latency,
        "baseline_right_latency": session.right_mean_latency,
        "assessment_time": session.completed_at.isoformat() if session.completed_at else None,
        "medication_state": None,
        "quality_metadata": {
            "total_cues": server_metrics.get("total_cues"),
            "correct_count": server_metrics.get("correct_count"),
            "missed_count": server_metrics.get("missed_count"),
            "validation_warnings": audit.get("validation_warnings", []),
            "metrics_version": session.metrics_version,
            "input_source": session.input_source,
        },
        "note": (
            "由 Calibration 会话自动生成；数值来自真实训练事件。"
            if session.input_source == "HUMAN_KEYBOARD"
            else f"由 Calibration 会话自动生成，但按键事件来源为 {session.input_source}，"
            "不是真人测量值，仅供流程演示，不得作为临床或科研基线使用。"
        ),
    }

    # Deactivate previous baselines of the same type, keep the rows.
    previous = db.execute(
        select(Baseline).where(
            Baseline.patient_id == session.patient_id,
            Baseline.baseline_type == "PIANO_CALIBRATION",
            Baseline.is_active.is_(True),
        )
    ).scalars().all()
    for row in previous:
        row.is_active = False

    baseline = Baseline(
        patient_id=session.patient_id,
        baseline_type="PIANO_CALIBRATION",
        source_id=session.id,
        snapshot_json=_dump(snapshot),
        algorithm_version=session.metrics_version,
        is_active=True,
        created_at=utcnow(),
    )
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    return baseline


def active_calibration(db: Session, patient_id: str) -> Baseline | None:
    return db.execute(
        select(Baseline)
        .where(
            Baseline.patient_id == patient_id,
            Baseline.baseline_type == "PIANO_CALIBRATION",
            Baseline.is_active.is_(True),
        )
        .order_by(Baseline.created_at.desc())
    ).scalars().first()


def list_sessions(
    db: Session, patient_id: str, *, page: int = 1, page_size: int = 20
) -> tuple[list[PianoSession], int]:
    total = db.execute(
        select(func.count())
        .select_from(PianoSession)
        .where(PianoSession.patient_id == patient_id)
    ).scalar_one()
    stmt = (
        select(PianoSession)
        .where(PianoSession.patient_id == patient_id)
        .order_by(PianoSession.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.execute(stmt).scalars().all()), int(total)
