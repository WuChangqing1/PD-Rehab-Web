"""Ballet-based movement training: exercise definitions.

WHY BALLET
==========
The module used to be five generic yoga poses. Ballet training is built on
exactly the things this patient group needs and the old set did not address:
external rhythm, explicit counts, decomposed movement, slow tempo, mirrored arm
lines and weight transfer. The session is therefore not "record a video and get
an angle" -- it is a guided, counted, accompanied task, and every exercise below
carries the cue sequence that drives it.

WHAT THESE DEFINITIONS ARE NOT
==============================
They are not a treatment claim. Nothing here says ballet improves a symptom, and
no exercise carries an expected clinical outcome. The training plan document
(`docs/ballet_training_rationale.md`) holds the reasoning; this file holds what
the software does.

Display scores (completion / ROM / symmetry / stability) may only be stored once
their formulas are fixed and versioned; until then they stay NULL, so no invented
0-100 number can reach the database or the UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import settings
from app.ml.registry import ModelState, ModelStatus

MODEL_NAME = "mediapipe_pose"
POSE_METRICS_VERSION = settings.pose_metrics_version

# Bumped whenever the exercise set, its cues or its metric mapping changes.
EXERCISE_DEFINITION_VERSION = "ballet-exercises-v1.0.0"

SAFETY_NOTICE = "请在医生或工作人员指导下完成。如出现疼痛、头晕或明显不适，请立即停止。"

# How the patient performs the exercise. Chosen by the doctor, never by the
# patient, and stored on the session so a result can be read in context.
EXECUTION_MODE_SEATED = "SEATED"
EXECUTION_MODE_STANDING_SUPPORTED = "STANDING_SUPPORTED"

EXECUTION_MODES: tuple[str, ...] = (EXECUTION_MODE_SEATED, EXECUTION_MODE_STANDING_SUPPORTED)

EXECUTION_MODE_LABELS: dict[str, str] = {
    EXECUTION_MODE_SEATED: "坐姿",
    EXECUTION_MODE_STANDING_SUPPORTED: "站姿（扶椅）",
}

# Which joint series drives the repetition count for each exercise.
DRIVE_SHOULDER = "shoulder_abduction"
DRIVE_TRUNK_TILT = "trunk_tilt"
DRIVE_KNEE = "knee_extension"
DRIVE_HIP = "hip_abduction"


@dataclass
class CueStep:
    """One spoken/displayed instruction inside a counted phrase."""

    text: str
    # How many beats this step lasts. The metronome counts them out loud.
    beats: int


@dataclass
class ExerciseDefinition:
    """One ballet training task."""

    key: str
    name_zh: str
    name_en: str
    description: str
    # Which parts of the body the exercise is about, in patient language.
    focus: list[str]
    joints: list[str]
    raw_metrics: list[str]
    drive_series: str
    supported_modes: list[str]
    # Rhythm the exercise is counted at when the doctor does not override it.
    default_bpm: int
    # The counted phrase the patient follows. Empty means "no cue sequence".
    cues: list[CueStep] = field(default_factory=list)
    # Beats the patient holds the end position before returning.
    hold_beats: int = 4
    hold_time_sec: float | None = None
    target_repetitions: int | None = None
    # Chair or wall support is assumed unless this is False.
    support_required: bool = True
    contraindications: list[str] = field(default_factory=list)
    # Score formulas. None means "not defined yet" -> the score must stay NULL.
    completion_formula: str | None = None
    rom_formula: str | None = None
    symmetry_formula: str | None = None
    stability_formula: str | None = None

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

    @property
    def total_beats(self) -> int:
        """Length of one complete repetition, in beats."""
        return sum(step.beats for step in self.cues) + self.hold_beats

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scores_available"] = self.scores_available
        d["total_beats"] = self.total_beats
        d["mode_labels"] = {m: EXECUTION_MODE_LABELS[m] for m in self.supported_modes}
        return d


# Raw metrics common to every exercise (spec V2 section 28) plus the per-side
# detail the analyser stores. The list is a contract: the analyser must produce
# exactly these keys.
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

# Leg exercises add knee and hip range, which the shoulder-based metrics cannot
# describe. These are additive: no existing metric definition changed.
_LEG_RAW_METRICS = _COMMON_RAW_METRICS + [
    "left_knee_max_angle_deg",
    "right_knee_max_angle_deg",
    "left_hip_abduction_deg",
    "right_hip_abduction_deg",
]

EXERCISES: tuple[ExerciseDefinition, ...] = (
    ExerciseDefinition(
        key="BALLET_PORT_DE_BRAS",
        name_zh="芭蕾手臂组合",
        name_en="Port de Bras",
        description="坐直或站稳，双臂随节拍缓慢抬起并打开，再缓慢回落。",
        focus=["手臂活动范围", "左右协调", "动作流畅性", "节奏"],
        joints=["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "trunk"],
        raw_metrics=_COMMON_RAW_METRICS,
        drive_series=DRIVE_SHOULDER,
        supported_modes=[EXECUTION_MODE_SEATED, EXECUTION_MODE_STANDING_SUPPORTED],
        default_bpm=60,
        cues=[
            CueStep("双臂缓慢抬起", 4),
            CueStep("向外打开", 4),
            CueStep("缓慢回落", 4),
        ],
        hold_beats=4,
        hold_time_sec=4.0,
        target_repetitions=4,
        support_required=False,
        contraindications=["肩关节急性疼痛"],
    ),
    ExerciseDefinition(
        key="BALLET_FIRST_POSITION",
        name_zh="第一位姿态保持",
        name_en="First Position Posture Hold",
        description="脚跟并拢、脚尖向外，双臂在身前形成圆形，保持躯干直立。",
        focus=["躯干直立", "左右对称", "稳定性", "保持时间"],
        joints=["left_shoulder", "right_shoulder", "left_hip", "right_hip", "trunk"],
        raw_metrics=_COMMON_RAW_METRICS,
        drive_series=DRIVE_SHOULDER,
        supported_modes=[EXECUTION_MODE_STANDING_SUPPORTED, EXECUTION_MODE_SEATED],
        default_bpm=60,
        cues=[
            CueStep("双臂抬至身前圆形", 4),
        ],
        hold_beats=8,
        hold_time_sec=8.0,
        target_repetitions=3,
        contraindications=["体位性低血压", "站立不稳且无支撑"],
    ),
    ExerciseDefinition(
        key="BALLET_TENDU",
        name_zh="伸腿点地",
        name_en="Tendu",
        description="扶椅站稳，一条腿沿地面缓慢伸出、脚尖点地，再缓慢收回。",
        focus=["腿部伸展", "重心转移", "活动范围", "左右差异"],
        joints=["left_hip", "right_hip", "left_knee", "right_knee", "trunk"],
        raw_metrics=_LEG_RAW_METRICS,
        drive_series=DRIVE_HIP,
        supported_modes=[EXECUTION_MODE_STANDING_SUPPORTED, EXECUTION_MODE_SEATED],
        default_bpm=60,
        cues=[
            CueStep("右腿缓慢伸出", 4),
            CueStep("脚尖点地", 2),
            CueStep("缓慢收回", 4),
        ],
        hold_beats=2,
        target_repetitions=4,
        contraindications=["髋关节急性疼痛", "站立不稳且无支撑"],
    ),
    ExerciseDefinition(
        key="BALLET_DEMI_PLIE",
        name_zh="半蹲",
        name_en="Demi-Plié",
        description="扶椅站稳，双膝缓慢弯曲至半蹲，再缓慢伸直。全程保持躯干直立。",
        focus=["膝髋屈曲", "左右对称", "稳定性", "节奏"],
        joints=["left_knee", "right_knee", "left_hip", "right_hip", "trunk"],
        raw_metrics=_LEG_RAW_METRICS,
        drive_series=DRIVE_KNEE,
        supported_modes=[EXECUTION_MODE_STANDING_SUPPORTED],
        default_bpm=50,
        cues=[
            CueStep("缓慢下蹲", 4),
            CueStep("缓慢伸直", 4),
        ],
        hold_beats=2,
        target_repetitions=5,
        contraindications=["膝关节急性疼痛", "半月板损伤", "站立不稳且无支撑"],
    ),
    ExerciseDefinition(
        key="BALLET_WEIGHT_SHIFT",
        name_zh="节奏性重心转移",
        name_en="Weight Shift with Port de Bras",
        description="随节拍把重心缓慢移向一侧，同时手臂向对侧打开，再移回另一侧。",
        focus=["重心转移", "全身协调", "左右对称", "节奏稳定性"],
        joints=["left_shoulder", "right_shoulder", "left_hip", "right_hip", "trunk"],
        raw_metrics=_COMMON_RAW_METRICS,
        drive_series=DRIVE_TRUNK_TILT,
        supported_modes=[EXECUTION_MODE_SEATED, EXECUTION_MODE_STANDING_SUPPORTED],
        default_bpm=60,
        cues=[
            CueStep("重心移向右侧", 4),
            CueStep("手臂向左侧打开", 4),
            CueStep("回到中间", 2),
            CueStep("重心移向左侧", 4),
            CueStep("手臂向右侧打开", 4),
        ],
        hold_beats=0,
        target_repetitions=4,
        support_required=False,
        contraindications=["体位性低血压"],
    ),
)

EXERCISE_BY_KEY: dict[str, ExerciseDefinition] = {e.key: e for e in EXERCISES}

# --------------------------------------------------------------------------- #
# Legacy exercise keys
# --------------------------------------------------------------------------- #
# The module shipped five yoga poses first, and recordings made then are still in
# the database. They are not deleted and they are not rewritten: a stored session
# keeps the exercise it was actually performed as. The UI shows them under a
# neutral label so an old row still reads correctly next to a new one.
LEGACY_EXERCISE_KEYS: tuple[str, ...] = (
    "MOUNTAIN_ARMS_UP",
    "ARMS_LATERAL_RAISE",
    "SIDE_BEND_STRETCH",
    "SEATED_TRUNK_ROTATION",
    "SEATED_ALTERNATING_ARM_RAISE",
)

LEGACY_EXERCISE_NAMES: dict[str, str] = {
    "MOUNTAIN_ARMS_UP": "双臂上举（早期动作）",
    "ARMS_LATERAL_RAISE": "侧平举（早期动作）",
    "SIDE_BEND_STRETCH": "侧屈伸展（早期动作）",
    "SEATED_TRUNK_ROTATION": "坐姿躯干旋转（早期动作）",
    "SEATED_ALTERNATING_ARM_RAISE": "交替抬臂（早期动作）",
}


def display_name(key: str) -> str:
    """Name to show for any stored exercise key, legacy ones included."""
    exercise = EXERCISE_BY_KEY.get(key)
    if exercise is not None:
        return exercise.name_zh
    return LEGACY_EXERCISE_NAMES.get(key, "历史训练记录")


def list_exercises(execution_mode: str | None = None) -> list[dict[str, Any]]:
    """All exercises, optionally only those valid for one execution mode."""
    items = EXERCISES
    if execution_mode:
        items = tuple(e for e in items if execution_mode in e.supported_modes)
    return [e.to_dict() for e in items]


def get_exercise(key: str) -> ExerciseDefinition | None:
    return EXERCISE_BY_KEY.get(key)


def drive_series_for(key: str) -> str | None:
    exercise = EXERCISE_BY_KEY.get(key)
    return exercise.drive_series if exercise else None


def current_status() -> ModelStatus:
    """Honest status for the movement training component.

    READY means the pipeline can actually run: mediapipe imports and the pose
    landmarker asset is present. The score formulas are still undefined, so
    `scores_available` stays False even when the pipeline is ready -- raw metrics
    and display scores are separate questions.
    """
    try:
        import mediapipe  # noqa: F401

        has_mediapipe = True
    except Exception:  # noqa: BLE001
        has_mediapipe = False

    model_path = settings.pose_landmarker_model_path
    model_present = model_path.is_file()
    pipeline_ready = has_mediapipe and model_present

    extra = {
        "mediapipe_installed": has_mediapipe,
        "landmarker_path": str(model_path),
        "landmarker_present": model_present,
        "expected_sha256": settings.pose_landmarker_sha256,
        "frame_stride": settings.pose_frame_stride,
        "max_frames": settings.pose_max_frames,
        "running_mode": "IMAGE (stateless; video-mode tracking drifts >60 deg on a "
                        "motionless subject, see app/ml/pose/landmarks.py)",
        "exercises_defined": len(EXERCISES),
        "exercise_definition_version": EXERCISE_DEFINITION_VERSION,
        "execution_modes": list(EXECUTION_MODES),
        "legacy_exercise_keys": list(LEGACY_EXERCISE_KEYS),
        "score_formulas_defined": all(e.scores_available for e in EXERCISES),
        "metrics_implemented": True,
        "raw_metrics_per_exercise": len(_COMMON_RAW_METRICS),
    }

    if not has_mediapipe:
        return ModelStatus(
            name=MODEL_NAME,
            version=POSE_METRICS_VERSION,
            state=ModelState.UNAVAILABLE,
            device=None,
            detail="MediaPipe 未安装，无法进行 Pose 关键点提取。",
            extra=extra,
        )

    if not model_present:
        return ModelStatus(
            name=MODEL_NAME,
            version=POSE_METRICS_VERSION,
            state=ModelState.UNAVAILABLE,
            device=None,
            detail=(
                f"未找到 MediaPipe Pose Landmarker 模型文件（期望路径 {model_path}）。"
                "放入 pose_landmarker_lite.task 后即可进行真实分析。"
            ),
            extra=extra,
        )

    return ModelStatus(
        name=MODEL_NAME,
        version=POSE_METRICS_VERSION,
        state=ModelState.READY if pipeline_ready else ModelState.UNAVAILABLE,
        device="cpu",
        detail=(
            "芭蕾动作分析就绪：MediaPipe Pose Landmarker（IMAGE 模式，逐帧独立推理）"
            f"+ 每 {settings.pose_frame_stride} 帧取样，输出原始指标与质量控制门限。"
            "展示分（completion / ROM / symmetry / stability）公式未定义，相关字段恒为空。"
        ),
        extra=extra,
    )
