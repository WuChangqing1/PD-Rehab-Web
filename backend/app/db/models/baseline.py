"""baselines (spec V2 section 33).

A baseline is a versioned snapshot. Setting a new baseline deactivates the
previous one but never deletes it, so history stays intact.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk, utcnow


class Baseline(Base, UUIDPk):
    __tablename__ = "baselines"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # BaselineType: COMPREHENSIVE | FINGER_TAPPING | PIANO_CALIBRATION | POSE
    baseline_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Reference to the record this snapshot was taken from (session / calibration id).
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Snapshot content. Must include:
    #   micro_expression / model_output, finger_tapping_left, finger_tapping_right,
    #   piano_calibration, medication_state, assessment_time, quality_metadata
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)

    algorithm_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )
