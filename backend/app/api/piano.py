"""Piano training endpoints (spec V2 section 48).

    POST /api/patients/{patient_id}/piano/calibration
    POST /api/patients/{patient_id}/piano/sessions
    POST /api/piano/sessions/{session_id}/events/batch
    POST /api/piano/sessions/{session_id}/complete
    GET  /api/patients/{patient_id}/piano/history

Raw events are posted as a batch and stored before metrics are computed, so the
summary is always reproducible from the stored events.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.core.errors import not_found
from app.schemas.common import Page
from app.schemas.piano import (
    CalibrationBaselineRead,
    PianoCalibrationRequest,
    PianoCompleteRequest,
    PianoEventRead,
    PianoEventsBatch,
    PianoSessionCreate,
    PianoSessionDetail,
    PianoSessionRead,
)
from app.services import audit_service, piano_service

router = APIRouter(tags=["Piano"])


@router.post(
    "/patients/{patient_id}/piano/calibration",
    response_model=PianoSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="开始钢琴 Calibration（30-60 秒，建立个人基线）",
)
def start_calibration(
    patient_id: str,
    payload: PianoCalibrationRequest,
    db: DbSession,
    user: CurrentUser,
) -> PianoSessionRead:
    """Open a calibration round.

    Calibration seeds the personal baseline that initial training difficulty is
    derived from. It is deliberately independent of any model output
    (spec V2 section 20).
    """
    difficulty = payload.difficulty.model_copy(update={"session_duration_sec": payload.duration_sec})
    session = piano_service.create_session(
        db,
        patient_id,
        PianoSessionCreate(
            mode="CALIBRATION",
            round_number=0,
            difficulty=difficulty,
            weak_hand=None,
            input_source=payload.input_source,
        ),
    )
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PIANO_CALIBRATION_START",
        entity_type="piano_session",
        entity_id=session.id,
        detail={"patient_id": patient_id, "duration_sec": payload.duration_sec},
    )
    return PianoSessionRead.model_validate(session)


@router.post(
    "/patients/{patient_id}/piano/sessions",
    response_model=PianoSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="开始一轮钢琴训练（记录本轮难度参数）",
)
def start_session(
    patient_id: str,
    payload: PianoSessionCreate,
    db: DbSession,
    user: CurrentUser,
) -> PianoSessionRead:
    session = piano_service.create_session(db, patient_id, payload)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PIANO_SESSION_START",
        entity_type="piano_session",
        entity_id=session.id,
        detail={
            "patient_id": patient_id,
            "mode": payload.mode,
            "round_number": payload.round_number,
            "bpm": payload.difficulty.bpm,
        },
    )
    return PianoSessionRead.model_validate(session)


@router.post(
    "/piano/sessions/{session_id}/events/batch",
    summary="批量保存原始按键事件（Raw Event 优先）",
)
def store_events(
    session_id: str,
    payload: PianoEventsBatch,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Store raw events verbatim.

    Raw events take priority over any total score (spec V2 section 17), so
    nothing here is filtered or recomputed on the way in.
    """
    stored, _events = piano_service.store_events(db, session_id, payload)
    return {
        "session_id": session_id,
        "stored": stored,
        "planned_cues": payload.planned_cues,
        "message": "原始事件已保存。指标将在 complete 时由服务端从这些事件重新计算。",
    }


@router.post(
    "/piano/sessions/{session_id}/complete",
    response_model=PianoSessionDetail,
    summary="结束本轮训练：服务端重算指标并记录难度调整",
)
def complete_session(
    session_id: str,
    payload: PianoCompleteRequest,
    db: DbSession,
    user: CurrentUser,
) -> PianoSessionDetail:
    session, computed = piano_service.complete_session(db, session_id, payload)

    baseline = None
    if session.mode == "CALIBRATION":
        baseline = piano_service.save_calibration_baseline(db, session)

    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PIANO_SESSION_COMPLETE",
        entity_type="piano_session",
        entity_id=session.id,
        detail={
            "mode": session.mode,
            "round_number": session.round_number,
            "warnings": computed["warnings"][:8],
            "baseline_created": baseline is not None,
        },
    )
    return _detail(db, session)


@router.get(
    "/piano/sessions/{session_id}",
    response_model=PianoSessionDetail,
    summary="训练会话详情（含原始事件）",
)
def get_session(session_id: str, db: DbSession, user: CurrentUser) -> PianoSessionDetail:
    session = piano_service.get_session(db, session_id)
    return _detail(db, session)


@router.get(
    "/patients/{patient_id}/piano/history",
    response_model=Page[PianoSessionRead],
    summary="钢琴训练历史",
)
def history(
    patient_id: str,
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Page[PianoSessionRead]:
    sessions, total = piano_service.list_sessions(
        db, patient_id, page=page, page_size=page_size
    )
    return Page[PianoSessionRead](
        items=[PianoSessionRead.model_validate(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/patients/{patient_id}/piano/baseline",
    response_model=CalibrationBaselineRead,
    summary="当前生效的钢琴 Calibration 基线",
)
def current_baseline(
    patient_id: str, db: DbSession, user: CurrentUser
) -> CalibrationBaselineRead:
    baseline = piano_service.active_calibration(db, patient_id)
    if baseline is None:
        raise not_found(
            "该患者尚无钢琴 Calibration 基线。请先完成一次 Calibration。",
            {"patient_id": patient_id},
        )
    snapshot = {}
    if baseline.snapshot_json:
        import json

        try:
            snapshot = json.loads(baseline.snapshot_json)
        except json.JSONDecodeError:
            snapshot = {}
    return CalibrationBaselineRead(
        id=baseline.id,
        patient_id=baseline.patient_id,
        baseline_accuracy=snapshot.get("baseline_accuracy"),
        baseline_response_latency=snapshot.get("baseline_response_latency"),
        baseline_response_latency_cv=snapshot.get("baseline_response_latency_cv"),
        baseline_timing_mae=snapshot.get("baseline_timing_mae"),
        baseline_left_accuracy=snapshot.get("baseline_left_accuracy"),
        baseline_right_accuracy=snapshot.get("baseline_right_accuracy"),
        baseline_left_latency=snapshot.get("baseline_left_latency"),
        baseline_right_latency=snapshot.get("baseline_right_latency"),
        created_at=baseline.created_at,
        algorithm_version=baseline.algorithm_version,
        is_active=baseline.is_active,
        snapshot=snapshot,
    )


def _detail(db, session) -> dict:
    """Session plus its full raw event stream, as plain data.

    Built from the service's joined view rather than from the ORM relationship,
    because the wrong-key flag and sequence position live in the session's audit
    JSON and are not columns.
    """
    base = PianoSessionRead.model_validate(session).model_dump()
    meta = {}
    if session.difficulty_before_json:
        import json

        try:
            meta = json.loads(session.difficulty_before_json)
        except json.JSONDecodeError:
            meta = {}

    base["events"] = [
        {
            **event,
            "id": None,
            "session_id": session.id,
            "created_at": None,
        }
        for event in piano_service.event_dicts(db, session)
    ]
    base["planned_cues"] = (meta.get("events_meta") or {}).get("planned_cues")
    return base
