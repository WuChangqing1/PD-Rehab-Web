"""Finger Tapping model status and feature schema constants.

Phase 1 scope: report honest availability and pin the feature schema.
The real pipeline (OpenCV -> MediaPipe -> time series -> QC -> features)
lands in Phase 4 and requires mediapipe + opencv, which are deliberately not
installed yet.

Algorithm semantics are taken from the external repository
D:\\CodingData\\Github\\VideoBased-PD-Biomarkers (Apache-2.0, unmodified).
See docs/metric_definitions.md section 1 and NOTICE.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.ml.registry import ModelState, ModelStatus

MODEL_NAME = "finger_tapping"
FEATURE_ALGORITHM_VERSION = settings.ft_feature_algorithm_version
QC_ALGORITHM_VERSION = settings.ft_qc_algorithm_version
COMPARE_ALGORITHM_VERSION = settings.ft_compare_algorithm_version

# Expected sha256 of the MediaPipe hand landmarker shipped with the external repo.
EXPECTED_LANDMARKER_SHA256 = (
    "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
)

# Finger Tapping feature keys (spec V2 section 41).
FEATURE_KEYS = (
    "tapping_frequency",
    "avg_amplitude",
    "avg_speed",
    "avg_cycle_duration",
    "amplitude_cv",
    "speed_cv",
    "cycle_cv",
    "amplitude_slope",
    "speed_slope",
    "cycle_slope",
    "interruptions",
    "valid_frame_ratio",
    "avg_landmark_confidence",
)

# Fields that must never be populated without a real, verified model.
ALWAYS_NULL_KEYS = ("severity_score", "severity_label")

# Analysis configuration snapshot. Stored per analysis so a single run is
# reproducible (spec V2 section 11.7).
ANALYSIS_CONFIG: dict[str, object] = {
    "normalization_method": "PALM_REFERENCE",
    "filter_method": "BUTTERWORTH",
    "filter_order": 4,
    "filter_cutoff_hz": 9.0,
    "filter_fs_source": "video_fps",
    "peak_distance": 5,
    "peak_height_factor": 0.5,
    "peak_prominence_factor": 0.5,
    "interruption_threshold_factor": 1.5,
    "interruption_threshold_basis": "median_cycle_duration",
    "interruption_rule_version": "v1.0.0",
    "min_valid_frame_ratio": 0.5,
    "min_cycle_count": 2,
    "min_frames_per_fps": 4,
    # MediaPipe handedness follows the mirrored/webcam convention; the external
    # repository compares it directly without correction. Unverified -> TBD.
    "handedness_convention": "TBD",
    "algorithm_version": FEATURE_ALGORITHM_VERSION,
}


def _missing_dependencies() -> list[str]:
    """Which Phase 4 runtime dependencies are absent right now."""
    missing: list[str] = []
    for module, label in (("cv2", "opencv"), ("mediapipe", "mediapipe")):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001
            missing.append(label)
    return missing


def current_status() -> ModelStatus:
    """Honest status for the Finger Tapping component."""
    landmarker: Path = settings.mediapipe_model_path
    repo: Path = Path(settings.finger_tapping_repo_dir)
    missing = _missing_dependencies()

    extra = {
        "landmarker_path": str(landmarker),
        "landmarker_present": landmarker.is_file(),
        "landmarker_expected_sha256": EXPECTED_LANDMARKER_SHA256,
        "external_repo_dir": str(repo),
        "external_repo_present": repo.is_dir(),
        "feature_algorithm_version": FEATURE_ALGORITHM_VERSION,
        "qc_algorithm_version": QC_ALGORITHM_VERSION,
        "missing_runtime_dependencies": missing,
        "pipeline_implemented": False,
        "severity_model_present": False,
    }

    if missing:
        return ModelStatus(
            name=MODEL_NAME,
            version=FEATURE_ALGORITHM_VERSION,
            state=ModelState.UNAVAILABLE,
            device=None,
            detail=(
                "Finger Tapping 分析依赖尚未安装（"
                + "、".join(missing)
                + "），且完整流水线计划在 Phase 4 实现。"
            ),
            extra=extra,
        )

    return ModelStatus(
        name=MODEL_NAME,
        version=FEATURE_ALGORITHM_VERSION,
        state=ModelState.UNAVAILABLE,
        device=None,
        detail="依赖已就绪，但分析流水线尚未实现（计划于 Phase 4）。",
        extra=extra,
    )


def landmarker_status() -> ModelStatus:
    """Status of the MediaPipe hand landmarker asset."""
    landmarker: Path = settings.mediapipe_model_path
    present = landmarker.is_file()
    return ModelStatus(
        name="mediapipe_hand_landmarker",
        version="float16",
        state=ModelState.READY if present else ModelState.UNAVAILABLE,
        device="cpu",
        detail=(
            "MediaPipe Hand Landmarker 模型文件已就位。"
            if present
            else "未找到 hand_landmarker.task。可从外部仓库 src/demo/ 复制，"
                 "或由 MediaPipe 官方地址下载。"
        ),
        extra={
            "path": str(landmarker),
            "present": present,
            "expected_sha256": EXPECTED_LANDMARKER_SHA256,
        },
    )
