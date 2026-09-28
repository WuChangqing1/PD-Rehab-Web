"""patients (spec V2 section 37).

Field-set ruling (see docs/spec_conflicts.md C13):
  - `age` is intentionally NOT stored; it is derived from `birthday`.
  - `id_card` is intentionally NOT stored at all (data-safety decision).
  - V1-only emergency contact fields are kept; they are additive and harmless.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class Patient(Base, UUIDPk, Timestamped):
    __tablename__ = "patients"

    hospital_number: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Sex: MALE | FEMALE | OTHER | UNKNOWN
    sex: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # V1-only additive fields
    emergency_contact: Mapped[str | None] = mapped_column(String(128), nullable=True)
    emergency_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ---- Parkinson related ----
    # DominantHand: LEFT | RIGHT | AMBIDEXTROUS | UNKNOWN
    dominant_hand: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    # AffectedSide: LEFT | RIGHT | BILATERAL | UNKNOWN
    affected_side: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    diagnosis_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disease_duration_years: Mapped[float | None] = mapped_column(nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)

    current_medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_medication_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # MedicationState: ON | OFF | UNKNOWN. Must be preserved for longitudinal comparison.
    medication_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")

    # ---- other medical history ----
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    comorbidities: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    surgery_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    rehab_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    @property
    def age(self) -> int | None:
        """Derived age. Not persisted, so it can never go stale."""
        if not self.birthday:
            return None
        today = date.today()
        return (
            today.year
            - self.birthday.year
            - ((today.month, today.day) < (self.birthday.month, self.birthday.day))
        )
