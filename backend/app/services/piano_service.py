"""Piano training service.

Raw events are persisted before any metric is considered, so the summary can
always be recomputed. Metrics are computed here (authoritative) and the client's
copy is stored alongside for comparison; a divergence between the two means one
implementation drifted, which would otherwise silently corrupt a trend line.
"""

from __future__ import annotations

import json

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import conflict, not_found
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Baseline, Patient, PianoEvent, PianoSession
from app.schemas.piano import (
    NEW_RECIPE_BASE_MODES,
    PianoCompleteRequest,
    PianoEventsBatch,
    PianoSessionCreate,
)
from app.utils.metrics import clean_float
from app.utils.piano_metrics import compute_metrics, validation_warnings

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Where a posted event field is stored.
#
# A field is either a real column on `piano_events`, or it travels in the
# `events_extra_json` side channel inside the session's audit blob. Both lists are
# exported because `tests/test_piano_event_storage.py` asserts that every field
# `PianoEventIn` accepts appears in one of them.
#
# The failure this prevents is silent: a field added to the request schema and not
# added here is accepted, validated by Pydantic, and then dropped. Nothing raises.
# That is exactly how `pair_role` and `inter_hand_onset_diff_ms` were lost, which
# made a bimanual round report no hand synchrony at all.
# ---------------------------------------------------------------------------

#: Columns that exist on the `piano_events` table.
PIANO_EVENT_COLUMNS: tuple[str, ...] = (
    "session_id",
    "event_index",
    "cue_onset_time_ms",
    "target_time_ms",
    "actual_time_ms",
    "response_latency_ms",
    "timing_error_ms",
    "key_code",
    "note",
    "hand",
    "finger_hint",
    "key_down_time_ms",
    "key_up_time_ms",
    "hold_duration_ms",
    "is_correct",
    "is_missed",
)

#: Fields stored in `events_extra_json`, keyed by `event_index`.
EVENT_EXTRA_FIELDS: tuple[str, ...] = (
    "is_wrong_key",
    "cue_index",
    "sequence_position",
    "sequence_length",
    # Memory-rhythm fields. These were ALSO being dropped: `is_prompt` marks a row
    # as a demonstrated note rather than a question, and `compute_metrics` excludes
    # those rows from every denominator. Losing the flag on save meant a memory
    # round counted its own demonstrations as cues the patient failed to answer,
    # which inflates the miss rate with failures that never happened.
    "is_prompt",
    "memory_group",
    # Recipe fields (docs/05). No DB column, following the same design as the
    # others: they are additive metadata, and the raw timeline stays readable
    # without them.
    "recipe_id",
    "pair_role",
    "inter_hand_onset_diff_ms",
    "beat_in_bar",
    "is_accent",
    "tempo_segment",
    "target_hold_ms",
    "pair_id",
    "target_offset_ms",
    "cue_type",
)

CALIBRATION_MODE = "CALIBRATION"

# Bumped when the set of values a calibration produces changes. v1.1.0 added the
# uncued spontaneous-tempo measurement alongside the eight spec values.
CALIBRATION_VERSION = "piano-calibration-v1.1.0"

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
    if payload.client_request_id is not None:
        # SQLite ignores FOR UPDATE. A no-op update acquires its transaction's
        # write lock before any deduplication reads, across worker processes.
        if db.get_bind().dialect.name == "sqlite":
            db.execute(update(Patient).where(Patient.id == patient_id).values(
                hospital_number=Patient.hospital_number, updated_at=Patient.updated_at))
        else:
            db.execute(select(Patient.id).where(Patient.id == patient_id).with_for_update())
    _get_patient(db, patient_id)
    config = payload.difficulty.model_dump()
    if payload.client_request_id is not None:
        # A locking read also bypasses an older repeatable-read snapshot which
        # authentication may have opened before this request acquired the lock.
        candidates = db.scalars(select(PianoSession)
            .where(PianoSession.patient_id == patient_id).with_for_update())
        for previous in candidates:
            audit = _load(previous.difficulty_before_json) or {}
            if audit.get("client_request_id") != payload.client_request_id:
                continue
            if (previous.mode != payload.mode or previous.recipe_id != payload.recipe_id
                    or previous.input_source != payload.input_source
                    or previous.round_number != payload.round_number
                    or audit.get("seed") != payload.seed
                    or audit.get("weak_hand") != payload.weak_hand
                    or any(getattr(previous, name, audit.get(name)) != value
                           for name, value in config.items())):
                raise conflict("client_request_id 已用于不同的训练配置。")
            return previous

    session = PianoSession(
        patient_id=patient_id,
        training_plan_id=payload.training_plan_id,
        mode=payload.mode,
        recipe_id=payload.recipe_id,
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
                "client_request_id": payload.client_request_id,
                "recipe_algorithm_version": (
                    "piano-recipe-v2.0.0" if payload.recipe_id in NEW_RECIPE_BASE_MODES
                    else "piano-recipe-v1.0.0" if payload.recipe_id else None
                ),
            }
        ),
        difficulty_engine_version=settings.piano_difficulty_version,
        metrics_version=settings.piano_metrics_version,
        started_at=payload.started_at or utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str, *, for_update: bool = False) -> PianoSession:
    stmt = select(PianoSession).where(PianoSession.id == session_id)
    if for_update:
        if db.get_bind().dialect.name == "sqlite":
            db.execute(update(PianoSession).where(PianoSession.id == session_id)
                       .values(bpm=PianoSession.bpm))
        else:
            stmt = stmt.with_for_update()
        stmt = stmt.execution_options(populate_existing=True)
    session = db.execute(stmt).scalar_one_or_none()
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
    session = get_session(db, session_id, for_update=True)
    if session.completed_at is not None:
        raise conflict(
            "该训练会话已完成，无法再追加事件。", {"session_id": session_id}
        )

    rows: list[PianoEvent] = []
    plain: list[dict] = []
    # An upload retry must not duplicate the patient's timeline. event_index is
    # stable within a session; reject a changed retry rather than replacing raw
    # evidence with a different measurement.
    persisted = {e["event_index"]: e for e in _event_dicts(db, session, for_update=True)}
    for event in payload.events:
        data = event.model_dump()
        previous = persisted.get(data["event_index"])
        if previous is not None:
            if any(previous.get(key) != value for key, value in data.items()):
                raise conflict("相同 event_index 的原始事件内容不一致。",
                               {"event_index": data["event_index"]})
            continue
        persisted[data["event_index"]] = data
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
    meta = existing.get("events_meta") or {}
    for name in ("planned_cues", "client_metrics", "input_latency_note"):
        value = getattr(payload, name)
        if value is not None:
            meta[name] = value
    meta["extra_event_fields"] = list(EVENT_EXTRA_FIELDS)
    existing["events_meta"] = meta
    if payload.spontaneous_tapping is not None:
        existing["spontaneous_tapping"] = payload.spontaneous_tapping.model_dump()
    if payload.raw_presses is not None:
        # Keep unscored input as well, without adding it to cue denominators.
        # An identical retry must not multiply raw presses. A later snapshot
        # may supply the release of a key that was still down in an earlier one.
        presses = {
            (p["key_code"], p["midi"], p["key_down_time_ms"]): p
            for p in existing.get("raw_presses", [])
        }
        for press in payload.raw_presses:
            data = press.model_dump()
            key = (data["key_code"], data["midi"], data["key_down_time_ms"])
            previous = presses.get(key)
            if previous is None or previous.get("key_up_time_ms") is None:
                presses[key] = data
            elif data["key_up_time_ms"] not in (None, previous["key_up_time_ms"]):
                raise conflict("重复原始按键的释放时间不一致。")
        existing["raw_presses"] = list(presses.values())
    existing["events_extra_json"] = _dump(
        [
            {
                "event_index": e["event_index"],
                **{name: e.get(name) for name in EVENT_EXTRA_FIELDS},
            }
            for e in persisted.values()
        ]
    )
    session.difficulty_before_json = _dump(existing)

    db.commit()
    logger.info("piano session %s: stored %d raw events", session_id[:8], len(rows))
    return len(rows), plain


def list_events(db: Session, session_id: str, *, for_update: bool = False) -> list[PianoEvent]:
    stmt = (
        select(PianoEvent)
        .where(PianoEvent.session_id == session_id)
        .order_by(PianoEvent.event_index)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return list(db.execute(stmt).scalars().all())


def _event_dicts(db: Session, session: PianoSession, *, for_update: bool = False) -> list[dict]:
    """Raw events as dicts, re-joined with the extra fields stored alongside."""
    rows = list_events(db, session.id, for_update=for_update)
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
        # Memory-rhythm marker. Defaults to False on old rows, which is correct:
        # a row stored before the flag existed was not a demonstration.
        event["is_prompt"] = bool(extra.get("is_prompt", False))
        event["memory_group"] = extra.get("memory_group")
        # Recipe fields, rejoined from the same side channel. Absent on rows
        # recorded before recipes existed, which reads as "no recipe" rather than
        # as a missing value to be filled in.
        event["recipe_id"] = extra.get("recipe_id")
        event["pair_role"] = extra.get("pair_role")
        event["inter_hand_onset_diff_ms"] = extra.get("inter_hand_onset_diff_ms")
        event["beat_in_bar"] = extra.get("beat_in_bar")
        event["is_accent"] = extra.get("is_accent")
        for name in ("tempo_segment", "target_hold_ms", "pair_id", "target_offset_ms", "cue_type"):
            event[name] = extra.get(name)
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

    # The rule engine runs in the frontend, so the version that actually produced
    # this decision is the one it reported, not the version this server expected
    # when the session was opened. Recording the expected value would make a
    # stored decision look like it came from an engine that never ran.
    decided_by = None
    if payload.adaptation:
        reported = payload.adaptation.get("engine_version")
        if isinstance(reported, str) and reported.strip():
            decided_by = reported.strip()
    if decided_by:
        if session.difficulty_engine_version not in (None, decided_by):
            logger.warning(
                "piano session %s: rule engine version %s overrides %s recorded at session start",
                session_id[:8],
                decided_by,
                session.difficulty_engine_version,
            )
        session.difficulty_engine_version = decided_by

    # Keep the recomputed metric set and quality warnings with the session.
    audit = _load(session.difficulty_before_json) or {}
    audit["server_metrics"] = metrics.to_dict()
    audit["completion_status"] = "INTERRUPTED" if payload.interrupted else "COMPLETED"
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

    # The patient's own tempo, measured in the uncued segment of calibration.
    # Stored alongside the eight spec values rather than inside them: the spec
    # lists eight, and this is an additional measurement with its own provenance
    # (docs/piano_training_plan.md P1). Absent means "not measured", never zero.
    spontaneous = audit.get("spontaneous_tapping") or {}
    spontaneous_rate = spontaneous.get("rate_hz")

    snapshot = {
        "baseline_accuracy": session.accuracy,
        "baseline_response_latency": session.mean_response_latency_ms,
        "baseline_response_latency_cv": session.response_latency_cv,
        "baseline_timing_mae": session.timing_mae_ms,
        "baseline_left_accuracy": session.left_accuracy,
        "baseline_right_accuracy": session.right_accuracy,
        "baseline_left_latency": session.left_mean_latency,
        "baseline_right_latency": session.right_mean_latency,
        "baseline_spontaneous_bpm": (
            clean_float(float(spontaneous_rate) * 60.0) if spontaneous_rate else None
        ),
        "baseline_spontaneous_interval_ms": clean_float(spontaneous.get("interval_ms")),
        "baseline_spontaneous_interval_cv": clean_float(spontaneous.get("interval_cv")),
        "baseline_spontaneous_tap_count": spontaneous.get("tap_count"),
        "calibration_version": CALIBRATION_VERSION,
        "assessment_time": session.completed_at.isoformat() if session.completed_at else None,
        "medication_state": None,
        "quality_metadata": {
            "total_cues": server_metrics.get("total_cues"),
            "correct_count": server_metrics.get("correct_count"),
            "missed_count": server_metrics.get("missed_count"),
            "validation_warnings": audit.get("validation_warnings", []),
            "metrics_version": session.metrics_version,
            "input_source": session.input_source,
            "spontaneous_window_ms": spontaneous.get("window_ms"),
            "spontaneous_note": spontaneous.get("note"),
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

    # A calibration that was not produced by a person must not become the
    # patient's ACTIVE baseline.
    #
    # The row is still written, because the flow test is worth keeping and the
    # snapshot carries the warning. But `is_active` is what `active_calibration`
    # reads, and the active baseline is what the training hub reports as
    # "基础能力测试已完成", what the difficulty engine scales from, and what the
    # report shows as the patient's measured ability.
    #
    # Leaving this to a UI warning was not enough. On the deployed database the
    # patient's active baseline -- accuracy 0.778, reaction 732 ms -- came from a
    # single SYNTHETIC_SELFTEST run, and every screen presented it as a completed
    # test. The app allows a `selftest=1` calibration on any patient, so this was
    # reachable in normal use, not only in seeded demo data.
    #
    # With the baseline inactive the surface reads "not yet measured", which is
    # true, and the doctor runs a real calibration. That is the honest outcome: a
    # synthetic round cannot invent an ability the patient never demonstrated.
    is_human = session.input_source == "HUMAN_KEYBOARD"

    baseline = Baseline(
        patient_id=session.patient_id,
        baseline_type="PIANO_CALIBRATION",
        source_id=session.id,
        snapshot_json=_dump(snapshot),
        algorithm_version=session.metrics_version,
        is_active=is_human,
        created_at=utcnow(),
    )
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    if not is_human:
        logger.warning(
            "piano session %s: calibration from %s stored INACTIVE; it cannot serve "
            "as the patient's baseline",
            session.id[:8],
            session.input_source,
        )
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
