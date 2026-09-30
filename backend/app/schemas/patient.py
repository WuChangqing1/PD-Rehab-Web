"""Patient schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.db.enums import AffectedSide, DominantHand, MedicationState, Sex
from app.schemas.common import ORMModel


class PatientBase(BaseModel):
    hospital_number: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    sex: Sex = Sex.UNKNOWN
    birthday: date | None = None
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=255)
    emergency_contact: str | None = Field(None, max_length=128)
    emergency_phone: str | None = Field(None, max_length=32)

    dominant_hand: DominantHand = DominantHand.UNKNOWN
    affected_side: AffectedSide = AffectedSide.UNKNOWN
    diagnosis_date: date | None = None
    disease_duration_years: float | None = Field(None, ge=0, le=100)
    current_stage: str | None = Field(None, max_length=64)

    current_medications: str | None = None
    last_medication_time: datetime | None = None
    medication_state: MedicationState = MedicationState.UNKNOWN

    medical_history: str | None = None
    comorbidities: str | None = None
    allergies: str | None = None
    surgery_history: str | None = None
    rehab_history: str | None = None
    doctor_notes: str | None = None

    @field_validator("birthday")
    @classmethod
    def _birthday_not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("出生日期不能晚于今天")
        return v

    @field_validator("diagnosis_date")
    @classmethod
    def _diagnosis_not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("确诊日期不能晚于今天")
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """All fields optional for PATCH."""

    hospital_number: str | None = Field(None, min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=128)
    sex: Sex | None = None
    birthday: date | None = None
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=255)
    emergency_contact: str | None = Field(None, max_length=128)
    emergency_phone: str | None = Field(None, max_length=32)

    dominant_hand: DominantHand | None = None
    affected_side: AffectedSide | None = None
    diagnosis_date: date | None = None
    disease_duration_years: float | None = Field(None, ge=0, le=100)
    current_stage: str | None = Field(None, max_length=64)

    current_medications: str | None = None
    last_medication_time: datetime | None = None
    medication_state: MedicationState | None = None

    medical_history: str | None = None
    comorbidities: str | None = None
    allergies: str | None = None
    surgery_history: str | None = None
    rehab_history: str | None = None
    doctor_notes: str | None = None


class PatientRead(ORMModel):
    id: str
    hospital_number: str
    name: str
    sex: str
    birthday: date | None
    age: int | None = None
    phone: str | None
    address: str | None
    emergency_contact: str | None
    emergency_phone: str | None

    dominant_hand: str
    affected_side: str
    diagnosis_date: date | None
    disease_duration_years: float | None
    current_stage: str | None

    current_medications: str | None
    last_medication_time: datetime | None
    medication_state: str

    medical_history: str | None
    comorbidities: str | None
    allergies: str | None
    surgery_history: str | None
    rehab_history: str | None
    doctor_notes: str | None

    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class PatientListItem(ORMModel):
    """Row shape for the patient list table."""

    id: str
    hospital_number: str
    name: str
    sex: str
    age: int | None = None
    affected_side: str
    dominant_hand: str
    disease_duration_years: float | None
    medication_state: str
    # Soft-deleted rows stay in the list when include_deleted is set; the UI uses
    # this to show the state and offer restore instead of the normal actions.
    is_deleted: bool = False
    last_assessment_at: datetime | None = None
    last_training_at: datetime | None = None
