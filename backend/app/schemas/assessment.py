"""Assessment session, media, micro-expression and finger tapping schemas.

Model-output fields are optional and default to None. They are only ever
filled from real adapter output; nothing here invents values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.enums import (
    AssessmentSessionType,
    FunctionalTestType,
    Hand,
    MediaType,
    MedicationState,
    SessionStatus,
)
from app.schemas.common import JsonText, ORMModel


# --------------------------------------------------------------------- session
class AssessmentSessionCreate(BaseModel):
    session_type: AssessmentSessionType = AssessmentSessionType.COMPREHENSIVE
    medication_state: MedicationState = MedicationState.UNKNOWN
    notes: str | None = None


class AssessmentSessionUpdate(BaseModel):
    medication_state: MedicationState | None = None
    status: SessionStatus | None = None
    notes: str | None = None


class AssessmentSessionRead(ORMModel):
    id: str
    patient_id: str
    session_type: str
    medication_state: str
    status: str
    created_by: str | None
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AssessmentSessionDetail(AssessmentSessionRead):
    """Session plus the child results attached to it."""

    micro_expression_results: list["MicroExpressionResultRead"] = Field(default_factory=list)
    finger_tapping_results: list["FingerTappingResultRead"] = Field(default_factory=list)
    functional_assessments: list["FunctionalAssessmentRead"] = Field(default_factory=list)


class AssessmentSessionComplete(BaseModel):
    notes: str | None = None


# ----------------------------------------------------------------------- media
class MediaFileRead(ORMModel):
    id: str
    patient_id: str
    assessment_session_id: str | None
    type: str
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    created_at: datetime


# ------------------------------------------------------------ micro expression
class TagScoreRead(BaseModel):
    name: str
    score: float


class MicroExpressionResultRead(ORMModel):
    id: str
    assessment_session_id: str
    media_file_id: str | None
    model_name: str | None
    model_version: str | None
    feature_schema_version: str
    predicted_class: str | None
    pd_probability: float | None
    dominant_tag: str | None
    tag_distribution: list[TagScoreRead] | None = None
    raw_output_json: JsonText = None
    inference_time_ms: int | None
    quality_json: JsonText = None
    created_at: datetime


class MicroExpressionAnalyzeRequest(BaseModel):
    """Metadata accompanying a micro-expression video upload."""

    medication_state: MedicationState = MedicationState.UNKNOWN
    recorded_at: datetime | None = None


# ------------------------------------------------------------- finger tapping
class FingerTappingAnalyzeRequest(BaseModel):
    hand: Hand
    medication_state: MedicationState = MedicationState.UNKNOWN


class FingerTappingResultRead(ORMModel):
    id: str
    assessment_session_id: str
    media_file_id: str | None
    hand: str
    input_source: str

    tapping_frequency: float | None
    avg_amplitude: float | None
    avg_speed: float | None
    avg_cycle_duration: float | None

    amplitude_cv: float | None
    speed_cv: float | None
    cycle_cv: float | None

    amplitude_slope: float | None
    speed_slope: float | None
    cycle_slope: float | None

    interruptions: int | None
    valid_frame_ratio: float | None
    avg_landmark_confidence: float | None

    severity_score: float | None
    severity_label: str | None

    analyzer_version: str | None
    feature_schema_version: str
    analysis_config_json: JsonText = None
    quality_json: JsonText = None
    raw_features_json: JsonText = None
    created_at: datetime


class LeftRightComparison(BaseModel):
    """Left/right summary for one session.

    Computed in the result layer; never stored on a single-hand row.
    `None` means one side is missing -- never substitute 0.
    """

    metric: str
    left: float | None
    right: float | None
    absolute_difference: float | None
    asymmetry_ratio: float | None


class FingerTappingSessionSummary(BaseModel):
    session_id: str
    left: FingerTappingResultRead | None = None
    right: FingerTappingResultRead | None = None
    comparisons: list[LeftRightComparison] = Field(default_factory=list)


# ------------------------------------------------------- functional assessment
class FunctionalAssessmentCreate(BaseModel):
    test_type: FunctionalTestType
    hand: Hand | None = None
    value_primary: float
    value_secondary: float | None = None
    unit: str = Field(..., min_length=1, max_length=32)
    medication_state: MedicationState = MedicationState.UNKNOWN
    notes: str | None = None
    performed_at: datetime
    assessment_session_id: str | None = None


class FunctionalAssessmentRead(ORMModel):
    id: str
    patient_id: str
    assessment_session_id: str | None
    test_type: str
    hand: str | None
    value_primary: float
    value_secondary: float | None
    unit: str
    medication_state: str
    notes: str | None
    performed_at: datetime
    created_by: str | None
    created_at: datetime


AssessmentSessionDetail.model_rebuild()
