from datetime import date, datetime
from pydantic import BaseModel, Field
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
    metrics: dict = Field(default_factory=dict)
    version: str | None


class FollowUpRead(BaseModel):
    patient_id: str
    start_date: date
    end_date: date
    offset_minutes: int
    is_showcase: bool = False
    assessments: list[AssessmentSessionRead]
    tapping: list[FingerTappingResultRead]
    piano: list[PianoSessionRead]
    pose: list[PoseSessionRead]
    guided: list[GuidedTrainingSummary]
