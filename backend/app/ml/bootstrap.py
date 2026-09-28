"""Model bootstrap: load every model once at startup and register its status.

Rules (spec V2 section 50):
  * Models are loaded once during app startup and then reused.
  * A failing model never prevents the application from starting.
  * A model that is not configured is reported as such, never as ready.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.finger_tapping import adapter as finger_tapping
from app.ml.micro_expression.adapter import analyzer as micro_expression_analyzer
from app.ml.pose import exercises as pose
from app.ml.registry import registry

logger = get_logger(__name__)


def _torch_device() -> tuple[str | None, dict]:
    """Report the inference device without pretending torch is installed."""
    info: dict = {"use_gpu_requested": settings.use_gpu, "torch_installed": False}
    try:
        import torch  # noqa: PLC0415

        info["torch_installed"] = True
        info["torch_version"] = torch.__version__
        info["torch_cuda_version"] = torch.version.cuda
        info["cuda_available"] = bool(torch.cuda.is_available())
        if settings.use_gpu and torch.cuda.is_available():
            info["device_name"] = torch.cuda.get_device_name(0)
            return f"cuda:0 ({info['device_name']})", info
        return "cpu", info
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
        return None, info


def load_all_models() -> None:
    """Called from the FastAPI lifespan. Never raises."""
    logger.info("loading models (one-time, at startup)")

    device, torch_info = _torch_device()
    logger.info(
        "inference device: %s (torch_installed=%s)",
        device or "unavailable",
        torch_info.get("torch_installed"),
    )

    # --- micro expression / PD auxiliary identification model ---
    status = micro_expression_analyzer.load()
    status.device = device
    status.extra.update(torch_info)
    registry.set(status)
    logger.info("micro_expression: %s", status.state)

    # --- finger tapping ---
    ft_status = finger_tapping.current_status()
    ft_status.device = device
    registry.set(ft_status)
    registry.set(finger_tapping.landmarker_status())
    logger.info("finger_tapping: %s", ft_status.state)

    # --- pose ---
    pose_status = pose.current_status()
    pose_status.device = device
    registry.set(pose_status)
    logger.info("pose: %s", pose_status.state)

    ready = [s.name for s in registry.all() if s.is_ready]
    logger.info(
        "model registry ready=%d/%d %s",
        len(ready),
        len(registry.all()),
        ready,
    )
