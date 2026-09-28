"""System endpoints: health, model status, GPU / device status.

The frontend dashboard and /system/model-status page read these. Values are
measured, never assumed: an unconfigured model is reported as unconfigured.
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import PROJECT_ROOT, settings
from app.db.models import (
    AssessmentSession,
    FingerTappingResult,
    MicroExpressionResult,
    Patient,
    PianoSession,
    PoseSession,
)
from app.ml.pose.exercises import list_exercises
from app.ml.registry import registry
from app.services import patient_service

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", summary="健康检查（无需登录）")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/models", summary="全部模型状态")
def models() -> dict:
    """Real status of every model. MODEL_NOT_CONFIGURED is a valid answer.

    Never reports READY for a component that cannot actually run, and never
    substitutes mock output.
    """
    return {
        "mock_mode": settings.demo_mock_mode,
        "summary": registry.summary(),
        "models": registry.to_dict(),
        "exercises": list_exercises(),
    }


@router.get("/gpu", summary="推理设备状态")
def gpu() -> dict:
    info: dict = {
        "use_gpu_requested": settings.use_gpu,
        "gpu_inference_concurrency": settings.gpu_inference_concurrency,
        "torch_installed": False,
        "cuda_available": False,
        "device": None,
        "device_name": None,
        "cuda_version": None,
        "driver_note": None,
    }
    try:
        import torch  # noqa: PLC0415

        info["torch_installed"] = True
        info["torch_version"] = torch.__version__
        info["cuda_version"] = torch.version.cuda
        info["cudnn_version"] = torch.backends.cudnn.version()
        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["device"] = "cuda:0"
            info["device_name"] = torch.cuda.get_device_name(0)
            capability = torch.cuda.get_device_capability(0)
            info["compute_capability"] = f"{capability[0]}.{capability[1]}"
        else:
            info["device"] = "cpu"
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["device"] = "cpu"
        info["driver_note"] = (
            "PyTorch 未安装。本机 GPU 为 RTX 5070 Laptop（Blackwell, sm_120），"
            "如需 GPU 推理请安装 cu128 或 cu130 版本的 PyTorch；"
            "cu126 不含 sm_120 kernel，不可使用。"
        )
    return info


@router.get("/info", summary="运行环境信息")
def info(db: DbSession, user: CurrentUser) -> dict:
    def count(model) -> int:
        return int(db.execute(select(func.count()).select_from(model)).scalar_one())

    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "project_root": str(PROJECT_ROOT),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "database_url_scheme": settings.database_url.split("://", 1)[0],
        "mock_mode": settings.demo_mock_mode,
        "counts": {
            "patients": count(Patient),
            "assessment_sessions": count(AssessmentSession),
            "micro_expression_results": count(MicroExpressionResult),
            "finger_tapping_results": count(FingerTappingResult),
            "piano_sessions": count(PianoSession),
            "pose_sessions": count(PoseSession),
        },
    }


@router.get("/dashboard", summary="Dashboard 汇总")
def dashboard(db: DbSession, user: CurrentUser) -> dict:
    """Counts, recent activity and model readiness for the dashboard page."""
    counts = patient_service.patient_counts(db)
    counts.update(patient_service.today_counts(db))

    recent_patients = patient_service.recent_patients(db, limit=5)
    recent_sessions = patient_service.recent_assessments(db, limit=5)

    names = {
        p.id: p.name
        for p in db.execute(
            select(Patient).where(
                Patient.id.in_([s.patient_id for s in recent_sessions] or [""])
            )
        ).scalars().all()
    }

    return {
        "counts": counts,
        "recent_patients": [
            {
                "id": p.id,
                "name": p.name,
                "hospital_number": p.hospital_number,
                "age": p.age,
                "affected_side": p.affected_side,
                "medication_state": p.medication_state,
            }
            for p in recent_patients
        ],
        "recent_assessments": [
            {
                "id": s.id,
                "patient_id": s.patient_id,
                "patient_name": names.get(s.patient_id),
                "session_type": s.session_type,
                "status": s.status,
                "medication_state": s.medication_state,
                "created_at": s.created_at.isoformat(),
            }
            for s in recent_sessions
        ],
        "model_status": registry.summary(),
        "mock_mode": settings.demo_mock_mode,
    }
