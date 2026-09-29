"""Pose / movement training endpoints (spec V2 sections 27, 28, 48).

    GET  /api/pose/exercises                      five exercise definitions
    GET  /api/pose/thresholds                     quality-gate derivations
    POST /api/patients/{patient_id}/pose/sessions open a session
    GET  /api/patients/{patient_id}/pose/sessions history
    GET  /api/pose/sessions/{session_id}          one session
    POST /api/pose/sessions/{session_id}/analyze  upload a recording and analyse

A recording that fails a quality gate returns 422 with the measured quality
report, exactly as finger tapping does. The metrics that could be computed are
included in the detail so the operator can see why it was refused, but the
session is not presented as a measurement.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, ErrorCode
from app.schemas.common import Page
from app.schemas.pose import (
    PoseAnalysisResponse,
    PoseExerciseRead,
    PoseSessionCreate,
    PoseSessionRead,
    PoseThresholdsRead,
)
from app.services import audit_service, pose_service

router = APIRouter(tags=["Pose"])


@router.get(
    "/pose/exercises",
    response_model=list[PoseExerciseRead],
    summary="五个动作定义（含指标清单与展示分可用性）",
)
def list_exercises(user: CurrentUser) -> list[PoseExerciseRead]:
    return [PoseExerciseRead(**item) for item in pose_service.exercises_payload()]


@router.get(
    "/pose/thresholds",
    response_model=PoseThresholdsRead,
    summary="质量控制门限的取值来源",
)
def thresholds(user: CurrentUser) -> PoseThresholdsRead:
    return PoseThresholdsRead(**pose_service.thresholds_payload())


@router.post(
    "/patients/{patient_id}/pose/sessions",
    response_model=PoseSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="开始一次动作训练（记录动作类型与来源）",
)
def start_session(
    patient_id: str,
    payload: PoseSessionCreate,
    db: DbSession,
    user: CurrentUser,
) -> PoseSessionRead:
    session = pose_service.create_session(db, patient_id, payload)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="POSE_SESSION_START",
        entity_type="pose_session",
        entity_id=session.id,
        detail={
            "patient_id": patient_id,
            "exercise_type": payload.exercise_type,
            "input_source": payload.input_source,
        },
    )
    return PoseSessionRead.model_validate(session)


@router.get(
    "/patients/{patient_id}/pose/sessions",
    response_model=Page[PoseSessionRead],
    summary="动作训练历史",
)
def history(
    patient_id: str,
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Page[PoseSessionRead]:
    sessions, total = pose_service.list_sessions(
        db, patient_id, page=page, page_size=page_size
    )
    return Page[PoseSessionRead](
        items=[PoseSessionRead.model_validate(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/pose/sessions/{session_id}",
    response_model=PoseSessionRead,
    summary="动作训练会话详情",
)
def get_session(session_id: str, db: DbSession, user: CurrentUser) -> PoseSessionRead:
    return PoseSessionRead.model_validate(pose_service.get_session(db, session_id))


@router.post(
    "/pose/sessions/{session_id}/analyze",
    response_model=PoseAnalysisResponse,
    summary="上传动作视频并分析（真实 MediaPipe Pose 推理）",
)
async def analyze(
    session_id: str,
    db: DbSession,
    user: CurrentUser,
    video: UploadFile = File(..., description="一段完整的动作视频"),
) -> PoseAnalysisResponse:
    session = pose_service.get_session(db, session_id)
    content = await video.read()

    session, outcome, media = pose_service.analyze_pose_video(
        db,
        session_id,
        patient_id=session.patient_id,
        original_filename=video.filename,
        content=content,
        mime_type=video.content_type,
    )

    audit_service.record(
        db,
        staff_user_id=user.id,
        action="POSE_ANALYZE",
        entity_type="pose_session",
        entity_id=session_id,
        detail={
            "exercise_type": session.exercise_type,
            "accepted": outcome.accepted,
            "gate_failures": outcome.gate_failures,
            "repetition_count": outcome.metrics.get("repetition_count"),
        },
    )

    payload = PoseAnalysisResponse(
        session=PoseSessionRead.model_validate(session),
        accepted=outcome.accepted,
        gate_failures=outcome.gate_failures,
        warnings=outcome.warnings,
        quality=outcome.quality,
        message=(
            "分析完成，指标已保存。"
            if outcome.accepted
            else "本次录制未通过质量控制，指标仅供参考，不作为有效测量值。"
        ),
    )

    if not outcome.accepted:
        # 422 with the measured report, matching the finger tapping contract.
        raise APIError(
            422,
            ErrorCode.VALIDATION_ERROR,
            payload.message,
            {
                "gate_failures": outcome.gate_failures,
                "quality": outcome.quality,
                "warnings": outcome.warnings,
                "metrics": session.raw_metrics_json,
                "media_file_id": media.id,
            },
        )
    return payload
