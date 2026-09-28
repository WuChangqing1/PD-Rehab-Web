"""Assessment domain tables.

assessment_sessions, media_files, micro_expression_results,
finger_tapping_results, functional_assessments.

Schema source: spec V2 sections 38-41 and 46.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPk, utcnow


class AssessmentSession(Base, UUIDPk, Timestamped):
    """Parent record for one comprehensive assessment.

    A single session is the time anchor: micro-expression, finger tapping
    (left/right) and optional functional tests all point at it, so results
    from different moments can never be mistaken for the same assessment.
    """

    __tablename__ = "assessment_sessions"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # AssessmentSessionType: COMPREHENSIVE | MICRO_EXPRESSION_ONLY |
    #                        FINGER_TAPPING_ONLY | FUNCTIONAL_TEST
    session_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="COMPREHENSIVE"
    )
    # MedicationState: ON | OFF | UNKNOWN
    medication_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    # SessionStatus: PENDING | IN_PROGRESS | COMPLETED | ABORTED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    media_files: Mapped[list["MediaFile"]] = relationship(back_populates="assessment_session")
    micro_expression_results: Mapped[list["MicroExpressionResult"]] = relationship(
        back_populates="assessment_session"
    )
    finger_tapping_results: Mapped[list["FingerTappingResult"]] = relationship(
        back_populates="assessment_session"
    )
    functional_assessments: Mapped[list["FunctionalAssessment"]] = relationship(
        back_populates="assessment_session"
    )


class MediaFile(Base, UUIDPk):
    __tablename__ = "media_files"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assessment_sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # MediaType: MICRO_EXPRESSION_VIDEO | FINGER_TAPPING_VIDEO | POSE_VIDEO | REPORT
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stored path is always UUID-based; never a patient name.
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    assessment_session: Mapped["AssessmentSession | None"] = relationship(
        back_populates="media_files"
    )


class MicroExpressionResult(Base, UUIDPk):
    """Real model output only.

    `predicted_class`, `pd_probability`, `dominant_tag` and `tag_distribution_json`
    MUST stay NULL until a real model is configured and inspected. The system
    never fabricates model output (spec V2 section 5.3).
    """

    __tablename__ = "micro_expression_results"

    assessment_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    media_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True
    )

    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature_schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")

    # All four are NULL unless the real model actually emits them.
    predicted_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pd_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    dominant_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tag_distribution_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    inference_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    assessment_session: Mapped["AssessmentSession"] = relationship(
        back_populates="micro_expression_results"
    )


class FingerTappingResult(Base, UUIDPk):
    """One analyzed hand for one session.

    `severity_score` / `severity_label` MUST stay NULL: the upstream repository
    ships no pretrained severity classifier and has no inference entry point
    (verified in Phase 0; see docs/environment_report.md section 5).
    """

    __tablename__ = "finger_tapping_results"

    assessment_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    media_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True
    )
    # Hand: LEFT | RIGHT. Left and right are always stored separately.
    hand: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    tapping_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)

    avg_amplitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cycle_duration: Mapped[float | None] = mapped_column(Float, nullable=True)

    amplitude_cv: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_cv: Mapped[float | None] = mapped_column(Float, nullable=True)
    cycle_cv: Mapped[float | None] = mapped_column(Float, nullable=True)

    amplitude_slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    cycle_slope: Mapped[float | None] = mapped_column(Float, nullable=True)

    interruptions: Mapped[int | None] = mapped_column(Integer, nullable=True)

    valid_frame_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_landmark_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Always NULL until a real, verified severity model exists.
    severity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    analyzer_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature_schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    # Tunable thresholds snapshot, so a single analysis is reproducible.
    analysis_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_timeseries_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    assessment_session: Mapped["AssessmentSession"] = relationship(
        back_populates="finger_tapping_results"
    )


class FunctionalAssessment(Base, UUIDPk):
    """Externally administered functional tests.

    Values are recorded by staff. The system never computes or infers
    MDS-UPDRS / PDQ-39 scores (spec V2 sections 31.3-31.5).
    """

    __tablename__ = "functional_assessments"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assessment_sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # FunctionalTestType: NINE_HOLE_PEG | BOX_AND_BLOCK | HAND_COORDINATION |
    #                     MDS_UPDRS | PDQ39
    test_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    hand: Mapped[str | None] = mapped_column(String(8), nullable=True)

    value_primary: Mapped[float] = mapped_column(Float, nullable=False)
    value_secondary: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)

    medication_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    assessment_session: Mapped["AssessmentSession | None"] = relationship(
        back_populates="functional_assessments"
    )
