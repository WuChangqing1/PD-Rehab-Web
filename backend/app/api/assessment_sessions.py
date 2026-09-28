"""Assessment session, micro-expression and finger tapping endpoints.

Paths follow spec V2 section 48 exactly.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.db.enums import Hand, MedicationState
from app.db.models import FunctionalAssessment, MicroExpressionResult
from app.schemas.assessment import (
    AssessmentSessionComplete,
    AssessmentSessionCreate,
    AssessmentSessionDetail,
    AssessmentSessionRead,
    FingerTappingResultRead,
    FingerTappingSessionSummary,
    FunctionalAssessmentRead,
    MicroExpressionAnalyzeRequest,
    MicroExpressionResultRead,
)
from app.schemas.common import Page
from app.services import assessment_service, audit_service

router = APIRouter(tags=["Assessment"])


# ------------------------------------------------- patient scoped: sessions
@router.post(
    "/patients/{patient_id}/assessment-sessions",
    response_model=AssessmentSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建综合评估会话",
)
def create_session(
    patient_id: str,
    payload: AssessmentSessionCreate,
    db: DbSession,
    user: CurrentUser,
) -> AssessmentSessionRead:
    session = assessment_service.create_session(db, patient_id, payload, created_by=user.id)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="ASSESSMENT_SESSION_CREATE",
        entity_type="assessment_session",
        entity_id=session.id,
        detail={"patient_id": patient_id, "session_type": session.session_type},
    )
    return AssessmentSessionRead.model_validate(session)


@router.get(
    "/patients/{patient_id}/assessment-sessions",
    response_model=Page[AssessmentSessionRead],
    summary="患者评估会话列表",
)
def list_sessions(
    patient_id: str,
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Page[AssessmentSessionRead]:
    sessions, total = assessment_service.list_sessions(
        db, patient_id, page=page, page_size=page_size
    )
    return Page[AssessmentSessionRead](
        items=[AssessmentSessionRead.model_validate(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


# ------------------------------------------------------ session scoped: read
@router.get(
    "/assessment-sessions/{session_id}",
    response_model=AssessmentSessionDetail,
    summary="评估会话详情（含全部子结果）",
)
def get_session(session_id: str, db: DbSession, user: CurrentUser) -> AssessmentSessionDetail:
    session = assessment_service.get_session(db, session_id)
    micro = assessment_service.list_micro_expression(db, session_id)
    finger = assessment_service.list_finger_tapping(db, session_id)
    functional = list(
        db.execute(
            select(FunctionalAssessment)
            .where(FunctionalAssessment.assessment_session_id == session_id)
            .order_by(FunctionalAssessment.performed_at.desc())
        ).scalars().all()
    )

    detail = AssessmentSessionDetail.model_validate(session)
    detail.micro_expression_results = [
        MicroExpressionResultRead.model_validate(r) for r in micro
    ]
    detail.finger_tapping_results = [FingerTappingResultRead.model_validate(r) for r in finger]
    detail.functional_assessments = [
        FunctionalAssessmentRead.model_validate(r) for r in functional
    ]
    return detail


@router.post(
    "/assessment-sessions/{session_id}/complete",
    response_model=AssessmentSessionRead,
    summary="完成评估会话",
)
def complete_session(
    session_id: str,
    payload: AssessmentSessionComplete,
    db: DbSession,
    user: CurrentUser,
) -> AssessmentSessionRead:
    session = assessment_service.complete_session(db, session_id, payload.notes)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="ASSESSMENT_SESSION_COMPLETE",
        entity_type="assessment_session",
        entity_id=session.id,
    )
    return AssessmentSessionRead.model_validate(session)


# ------------------------------------------------------------ micro expression
@router.post(
    "/assessment-sessions/{session_id}/micro-expression",
    response_model=MicroExpressionResultRead,
    summary="微表情 / AI 视频分析（需要真实模型）",
)
async def analyze_micro_expression(
    session_id: str,
    db: DbSession,
    user: CurrentUser,
    video: UploadFile = File(..., description="mp4 / mov / avi"),
    medication_state: MedicationState = Form(MedicationState.UNKNOWN),
    recorded_at: str | None = Form(None),
) -> MicroExpressionResultRead:
    """Returns 503 MODEL_NOT_CONFIGURED while no real model is configured.

    The video is stored first (UUID filename) so the record of the attempt
    survives; no result row is created unless the real model produced output.
    """
    session = assessment_service.get_session(db, session_id)
    content = await video.read()
    payload = MicroExpressionAnalyzeRequest.model_validate(
        {"medication_state": medication_state, "recorded_at": recorded_at or None}
    )
    row, _media = assessment_service.analyze_micro_expression(
        db,
        session_id,
        patient_id=session.patient_id,
        original_filename=video.filename,
        content=content,
        payload=payload,
        created_by=user.id,
    )
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="MICRO_EXPRESSION_ANALYZE",
        entity_type="micro_expression_result",
        entity_id=row.id,
    )
    return MicroExpressionResultRead.model_validate(row)


@router.get(
    "/assessment-sessions/{session_id}/micro-expression",
    response_model=list[MicroExpressionResultRead],
    summary="微表情分析结果列表",
)
def list_micro_expression(
    session_id: str, db: DbSession, user: CurrentUser
) -> list[MicroExpressionResultRead]:
    rows = assessment_service.list_micro_expression(db, session_id)
    return [MicroExpressionResultRead.model_validate(r) for r in rows]


# ------------------------------------------------------------ finger tapping
@router.post(
    "/assessment-sessions/{session_id}/finger-tapping",
    response_model=FingerTappingSessionSummary,
    summary="Finger Tapping 视频分析（单次一只手）",
)
async def analyze_finger_tapping(
    session_id: str,
    db: DbSession,
    user: CurrentUser,
    hand: Hand = Form(...),
    video: UploadFile = File(..., description="10-20 秒手指敲击视频"),
    medication_state: MedicationState = Form(MedicationState.UNKNOWN),
) -> FingerTappingSessionSummary:
    """Phase 1: the analysis pipeline is not implemented (Phase 4).

    The upload is stored, then the analysis job fails with NOT_IMPLEMENTED.
    No metric is invented and nothing is written to finger_tapping_results.

    The response always reflects the true state of the session so the UI can
    show whichever hand has already been analysed.
    """
    from app.schemas.assessment import FingerTappingAnalyzeRequest

    session = assessment_service.get_session(db, session_id)
    content = await video.read()
    payload = FingerTappingAnalyzeRequest(hand=hand, medication_state=medication_state)
    job, _media = assessment_service.analyze_finger_tapping(
        db,
        session_id,
        patient_id=session.patient_id,
        original_filename=video.filename,
        content=content,
        payload=payload,
        created_by=user.id,
    )
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="FINGER_TAPPING_ANALYZE",
        entity_type="assessment_session",
        entity_id=session_id,
        detail={"hand": str(hand), "job_id": job.job_id, "job_status": job.status},
    )
    if job.status == "FAILED" and job.error:
        from app.core.errors import APIError

        err = job.error.get("error", {})
        raise APIError(
            status.HTTP_501_NOT_IMPLEMENTED,
            err.get("code", "NOT_IMPLEMENTED"),
            err.get("message", "Finger Tapping 分析尚未实现。"),
            err.get("detail"),
        )
    return _session_summary(db, session_id)


@router.get(
    "/assessment-sessions/{session_id}/finger-tapping",
    response_model=FingerTappingSessionSummary,
    summary="Finger Tapping 结果（左右手 + 左右差异）",
)
def get_finger_tapping(
    session_id: str, db: DbSession, user: CurrentUser
) -> FingerTappingSessionSummary:
    return _session_summary(db, session_id)


def _session_summary(db, session_id: str) -> FingerTappingSessionSummary:
    assessment_service.get_session(db, session_id)
    rows = assessment_service.list_finger_tapping(db, session_id)
    left = next((r for r in rows if r.hand == str(Hand.LEFT)), None)
    right = next((r for r in rows if r.hand == str(Hand.RIGHT)), None)
    return FingerTappingSessionSummary(
        session_id=session_id,
        left=FingerTappingResultRead.model_validate(left) if left else None,
        right=FingerTappingResultRead.model_validate(right) if right else None,
        comparisons=assessment_service.compare_left_right(rows),
    )


# ------------------------------------------------------------------- helpers
def _json_or_none(text: str | None):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


_ = MicroExpressionResult  # keep the import explicit for type checkers
