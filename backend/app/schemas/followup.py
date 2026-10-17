from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.assessment import AssessmentSessionRead, FingerTappingResultRead
from app.schemas.piano import PianoSessionRead
from app.schemas.pose import PoseSessionRead


class GuidedTrainingSummary(BaseModel):
    id: str
    patient_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    source: str
    song_id: str | None
    selected_hand: str | None
    difficulty: str | None
    bpm: float | None
    segment_1_bpm: float | None = None
    segment_2_bpm: float | None = None
    metrics: dict = Field(default_factory=dict)
    version: str | None


class PianoTrainingSummary(PianoSessionRead):
    @field_validator('difficulty_before_json')
    @classmethod
    def summary_audit(cls, value):
        if not isinstance(value,dict):
            return None
        fields={'bpm','judgement_window_ms','sequence_length','note_density','hand_mode',
                'weak_side_ratio','finger_complexity','session_duration_sec','tempo_ceiling_bpm',
                'weak_hand','recipe_algorithm_version','completion_status','server_metrics'}
        return {key:item for key,item in value.items() if key in fields}


class FollowUpRead(BaseModel):
    patient_id: str
    start_date: date
    end_date: date
    offset_minutes: int
    is_showcase: bool = False
    exercise_names: dict[str,str]
    assessments: list[AssessmentSessionRead]
    tapping: list[FingerTappingResultRead]
    piano: list[PianoTrainingSummary]
    pose: list[PoseSessionRead]
    guided: list[GuidedTrainingSummary]
