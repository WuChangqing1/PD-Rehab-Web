"""Pose / movement training model status and exercise definitions.

Phase 1 scope: report honest availability and define the five exercises.
Metric computation lands in Phase 6.

The five exercises come from spec V2 section 27. Display scores
(completion / ROM / symmetry / stability) may only be stored once their
formulas are fixed and versioned here; until then they stay NULL, so no
invented 0-100 numbers can reach the database or the UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import settings
from app.ml.registry import ModelState, ModelStatus

MODEL_NAME = "mediapipe_pose"
POSE_METRICS_VERSION = settings.pose_metrics_version

# Bumped whenever any score formula below changes.
EXERCISE_DEFINITION_VERSION = "pose-exercises-v0.1.0-draft"

SAFETY_NOTICE = (
    "请在医生或工作人员指导下完成。如出现疼痛、头晕或明显不适，请立即停止。"
)


@dataclass
class ExerciseDefinition:
    """One movement exercise."""

    key: str
    name_zh: str
    description: str
    joints: list[str]
    raw_metrics: list[str]
    # Score formulas. None means "not defined yet" -> the score must stay NULL.
    completion_formula: str | None = None
    rom_formula: str | None = None
    symmetry_formula: str | None = None
    stability_formula: str | None = None
    hold_time_sec: float | None = None
    target_repetitions: int | None = None
    contraindications: list[str] = field(default_factory=list)

    @property
    def scores_available(self) -> bool:
        """True only when every display score has a defined formula."""
        return all(
            f is not None
            for f in (
                self.completion_formula,
                self.rom_formula,
                self.symmetry_formula,
                self.stability_formula,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scores_available"] = self.scores_available
        return d


# Raw metrics common to all exercises (spec V2 section 28).
_COMMON_RAW_METRICS = [
    "left_shoulder_max_angle_deg",
    "right_shoulder_max_angle_deg",
    "left_right_angle_difference_deg",
    "trunk_angle_deg",
    "hold_time_sec",
    "repetition_count",
    "repetition_interval_ms",
    "movement_speed_deg_per_sec",
    "angle_std_deg",
    "valid_pose_frame_ratio",
]

EXERCISES: tuple[ExerciseDefinition, ...] = (
    ExerciseDefinition(
        key="MOUNTAIN_ARMS_UP",
        name_zh="山式双臂上举",
        description="站立或坐姿，双臂自身体两侧向上举过头顶，保持躯干直立。",
        joints=["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "trunk"],
        raw_metrics=_COMMON_RAW_METRICS,
        hold_time_sec=5.0,
        target_repetitions=5,
        contraindications=["肩关节急性疼痛", "未控制的高血压"],
    ),
    ExerciseDefinition(
        key="ARMS_LATERAL_RAISE",
        name_zh="双臂侧平举",
        description="双臂自身体两侧向外展开至与肩同高，保持后缓慢放下。",
        joints=["left_shoulder", "right_shoulder", "trunk"],
        raw_metrics=_COMMON_RAW_METRICS,
        hold_time_sec=5.0,
        target_repetitions=5,
    ),
    ExerciseDefinition(
        key="SIDE_BEND_STRETCH",
        name_zh="左右侧屈伸展",
        description="双臂上举或叉腰，躯干向左右两侧交替侧屈。",
        joints=["trunk", "left_shoulder", "right_shoulder", "left_hip", "right_hip"],
        raw_metrics=_COMMON_RAW_METRICS,
        target_repetitions=6,
        contraindications=["腰椎急性损伤", "体位性低血压"],
    ),
    ExerciseDefinition(
        key="SEATED_TRUNK_ROTATION",
        name_zh="坐姿躯干旋转",
        description="坐位，双手交叉抱于胸前，躯干向左右两侧交替旋转。",
        joints=["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
        raw_metrics=_COMMON_RAW_METRICS,
        target_repetitions=6,
        contraindications=["脊柱不稳", "严重骨质疏松"],
    ),
    ExerciseDefinition(
        key="SEATED_ALTERNATING_ARM_RAISE",
        name_zh="坐姿交替抬臂",
        description="坐位，左右手臂交替向前上方抬起，保持躯干稳定。",
        joints=["left_shoulder", "right_shoulder", "left_elbow", "right_elbow"],
        raw_metrics=_COMMON_RAW_METRICS,
        target_repetitions=8,
    ),
)

EXERCISE_BY_KEY: dict[str, ExerciseDefinition] = {e.key: e for e in EXERCISES}


def list_exercises() -> list[dict[str, Any]]:
    return [e.to_dict() for e in EXERCISES]


def get_exercise(key: str) -> ExerciseDefinition | None:
    return EXERCISE_BY_KEY.get(key)


def current_status() -> ModelStatus:
    """Honest status for the Pose component."""
    try:
        import mediapipe  # noqa: F401

        has_mediapipe = True
    except Exception:  # noqa: BLE001
        has_mediapipe = False

    return ModelStatus(
        name=MODEL_NAME,
        version=POSE_METRICS_VERSION,
        state=ModelState.UNAVAILABLE,
        device=None,
        detail=(
            "MediaPipe 未安装，且 Pose 指标计算计划在 Phase 6 实现。"
            if not has_mediapipe
            else "MediaPipe 已安装，但 Pose 指标计算尚未实现（计划于 Phase 6）。"
        ),
        extra={
            "mediapipe_installed": has_mediapipe,
            "exercises_defined": len(EXERCISES),
            "exercise_definition_version": EXERCISE_DEFINITION_VERSION,
            "score_formulas_defined": all(e.scores_available for e in EXERCISES),
            "metrics_implemented": False,
        },
    )
