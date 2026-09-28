"""Micro-expression / PD auxiliary identification model adapter.

HARD RULES (spec V2 sections 4.2, 5.3, 67; task brief section 8):
  * Never fabricate model output.
  * Never generate random tags or probabilities.
  * Never hardcode percentages seen in a mock-up.
  * Never guess the model structure from a requirements document.
  * Never train a substitute model and present it as the teacher's model.
  * Fields the real model does not emit must be null or absent.

The teacher's model has not been provided, so this adapter currently reports
MODEL_NOT_CONFIGURED and refuses to analyse.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import APIError, ErrorCode, model_not_configured
from app.core.logging import get_logger
from app.ml.registry import ModelState, ModelStatus

logger = get_logger(__name__)

MODEL_NAME = "micro_expression_model"
MODEL_VERSION = "unknown"

# Weight suffixes the adapter will look for once a directory is configured.
# Their presence is reported only; it does not imply the model is loadable.
_WEIGHT_SUFFIXES = (".pt", ".pth", ".ckpt", ".onnx", ".engine", ".safetensors", ".h5", ".bin")


@dataclass
class TagScore:
    """One entry of a tag distribution."""

    name: str
    score: float


@dataclass
class MicroExpressionResult:
    """Normalized adapter output.

    Only `model_name`, `model_version`, `feature_schema_version`,
    `raw_output_json`, `inference_time_ms` and `quality_json` are always
    populated. Everything else stays None unless the real model emits it.
    """

    model_name: str = MODEL_NAME
    model_version: str = MODEL_VERSION
    feature_schema_version: str = settings.feature_schema_version

    predicted_class: str | None = None
    pd_probability: float | None = None

    dominant_tag: str | None = None
    tag_distribution: list[TagScore] | None = None

    raw_output_json: dict[str, Any] = field(default_factory=dict)
    inference_time_ms: int | None = None
    quality_json: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.tag_distribution is None:
            d["tag_distribution"] = None
        return d


class MicroExpressionAnalyzer:
    """Business code depends only on this class, never on the model internals."""

    def __init__(self) -> None:
        self._status = ModelStatus(
            name=MODEL_NAME,
            version=MODEL_VERSION,
            state=ModelState.MODEL_NOT_CONFIGURED,
            device=None,
            detail="MICRO_EXPRESSION_MODEL_DIR 未配置",
        )
        self._model: Any = None

    # ------------------------------------------------------------------ status
    @property
    def status(self) -> ModelStatus:
        return self._status

    def refresh_status(self) -> ModelStatus:
        """Re-evaluate configuration state from disk. Cheap and side-effect free."""
        directory = settings.micro_expression_path
        if directory is None:
            self._status = ModelStatus(
                name=MODEL_NAME,
                version=MODEL_VERSION,
                state=ModelState.MODEL_NOT_CONFIGURED,
                device=None,
                detail=(
                    "未配置模型目录。请设置环境变量 MICRO_EXPRESSION_MODEL_DIR "
                    "并把老师提供的模型文件放入该目录。"
                ),
            )
            return self._status

        weights = sorted(
            p.name for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in _WEIGHT_SUFFIXES
        )
        if not weights:
            self._status = ModelStatus(
                name=MODEL_NAME,
                version=MODEL_VERSION,
                state=ModelState.UNAVAILABLE,
                device=None,
                detail=(
                    f"目录已配置（{directory}）但未找到权重文件"
                    f"（{'/'.join(_WEIGHT_SUFFIXES)}），模型不可用。"
                ),
            )
            return self._status

        # A directory with weights exists, but the adapter has no verified
        # load/inference implementation for it yet. Reporting READY here would
        # be a lie, so the state stays UNAVAILABLE until the model source has
        # actually been inspected and wired up.
        self._status = ModelStatus(
            name=MODEL_NAME,
            version=MODEL_VERSION,
            state=ModelState.UNAVAILABLE,
            device=None,
            detail=(
                f"检测到权重文件 {weights}，但适配层尚未接入该模型的加载与推理逻辑，"
                "模型当前不可用。"
            ),
        )
        return self._status

    # -------------------------------------------------------------------- load
    def load(self) -> ModelStatus:
        """Called once at application startup. Never raises."""
        status = self.refresh_status()
        if status.state is not ModelState.MODEL_NOT_CONFIGURED:
            logger.warning(
                "micro-expression model not loadable: %s", status.detail
            )
        else:
            logger.info("micro-expression model not configured (expected)")
        return status

    # ----------------------------------------------------------------- analyze
    def analyze(self, video_path: str) -> dict[str, Any]:
        """Analyse one video. Requires a real, configured model."""
        status = self.refresh_status()
        if status.state is ModelState.MODEL_NOT_CONFIGURED:
            raise model_not_configured(
                {
                    "env_var": "MICRO_EXPRESSION_MODEL_DIR",
                    "current_value": settings.micro_expression_model_dir,
                    "hint": (
                        "系统不会伪造模型输出。请提供老师模型的源码目录、checkpoint、"
                        "标签字典与 requirements 后重新配置。"
                    ),
                }
            )
        if status.state is not ModelState.READY:
            raise APIError(
                503,
                ErrorCode.MODEL_UNAVAILABLE,
                "微表情 / AI 模型当前不可用，无法进行分析。",
                {"detail": status.detail},
            )

        # Unreachable until a real model is wired up. Kept explicit so that a
        # future implementation cannot silently skip input validation.
        video = Path(video_path)
        if not video.is_file():
            raise APIError(
                400, ErrorCode.VIDEO_UNREADABLE, "视频文件不存在或不可读。",
                {"path": video_path},
            )

        started = time.perf_counter()
        raw = self._infer(video)  # pragma: no cover - no implementation yet
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return self._normalize(raw, elapsed_ms)

    def _infer(self, video: Path) -> dict[str, Any]:  # pragma: no cover
        raise APIError(
            503,
            ErrorCode.MODEL_LOAD_FAILED,
            "微表情模型推理尚未实现。",
            {"path": str(video)},
        )

    def _normalize(self, raw: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
        """Translate raw model output into the standard contract.

        Only copies fields the model actually produced; missing keys stay None.
        """
        tags = raw.get("tag_distribution") or raw.get("tags")
        distribution: list[TagScore] | None = None
        if isinstance(tags, list):
            distribution = [
                TagScore(name=str(t.get("name")), score=float(t.get("score")))
                for t in tags
                if isinstance(t, dict) and t.get("name") is not None
            ]

        result = MicroExpressionResult(
            predicted_class=raw.get("predicted_class"),
            pd_probability=raw.get("pd_probability"),
            dominant_tag=raw.get("dominant_tag"),
            tag_distribution=distribution,
            raw_output_json=raw,
            inference_time_ms=elapsed_ms,
            quality_json=raw.get("quality_json", {}),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return result.to_dict()


analyzer = MicroExpressionAnalyzer()
