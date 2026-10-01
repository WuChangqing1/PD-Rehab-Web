"""Pose training schemas (spec V2 sections 27, 28, 43).

Display scores are deliberately absent. The specification lists completion /
ROM / symmetry / stability as 0-100 values but never defines their formulas, so
the API neither accepts nor returns them: a number nobody can reproduce must not
be able to enter the database through this layer either.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import JsonText, ORMModel
from app.schemas.piano import InputSourceLiteral

ExerciseTypeLiteral = Literal[
    "BALLET_PORT_DE_BRAS",
    "BALLET_FIRST_POSITION",
    "BALLET_TENDU",
    "BALLET_DEMI_PLIE",
    "BALLET_WEIGHT_SHIFT",
]

# Chosen by the doctor before the task starts; the patient never picks it.
ExecutionModeLiteral = Literal["SEATED", "STANDING_SUPPORTED"]


class PoseSessionCreate(BaseModel):
    """Open a movement-training session for one exercise."""

    exercise_type: ExerciseTypeLiteral
    execution_mode: ExecutionModeLiteral = "SEATED"
    input_source: InputSourceLiteral = "HUMAN_KEYBOARD"
    difficulty: dict[str, Any] | None = None


class PoseSessionRead(ORMModel):
    id: str
    patient_id: str
    exercise_type: str
    execution_mode: str
    input_source: str
    difficulty_json: JsonText = None

    # Always NULL until a formula is defined and versioned.
    completion_score: float | None
    range_of_motion: float | None
    symmetry_score: float | None
    stability_score: float | None

    hold_time_sec: float | None
    repetition_count: int | None
    movement_speed: float | None
    valid_pose_frame_ratio: float | None

    raw_metrics_json: JsonText = None
    quality_json: JsonText = None
    algorithm_version: str | None
    exercise_definition_version: str | None
    media_file_id: str | None

    started_at: datetime | None
    completed_at: datetime | None


class PoseAnalysisResponse(BaseModel):
    """Result of analysing one recording.

    `accepted` is False when a quality gate refused the recording; the measured
    metrics are still returned so the reason is visible, but the session is not
    presented as a valid measurement.
    """

    session: PoseSessionRead
    accepted: bool
    gate_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    message: str


class ExerciseCueRead(BaseModel):
    """One step of the counted phrase the patient follows."""

    text: str
    beats: int


class PoseExerciseRead(BaseModel):
    """One ballet exercise, with its metrics, cues and honest score availability."""

    key: str
    name_zh: str
    name_en: str
    description: str
    # What the exercise trains, in patient language rather than joint names.
    focus: list[str]
    joints: list[str]
    raw_metrics: list[str]
    drive_series: str
    supported_modes: list[str]
    mode_labels: dict[str, str]
    default_bpm: int
    cues: list[ExerciseCueRead]
    hold_beats: int
    total_beats: int
    support_required: bool
    hold_time_sec: float | None
    target_repetitions: int | None
    contraindications: list[str]
    scores_available: bool
    score_formulas: dict[str, str | None]


class PoseThresholdsRead(BaseModel):
    """The derivations behind the quality gates, so a refusal can be explained."""

    min_valid_frame_ratio: float
    min_duration_sec: float
    min_landmark_visibility: float
    min_movement_range_deg: float
    algorithm_version: str
