"""Training domain tables: training_plans, piano_sessions, piano_events, pose_sessions.

training_plans comes from spec V1 section 29.7 (V2 references the FK but never
defines the table). See docs/spec_conflicts.md C20 and C23.

Piano naming follows V2 section 43: *_response_latency_* / *_latency*, never
reaction_time / rt (see docs/spec_conflicts.md C6).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPk, utcnow


class TrainingPlan(Base, UUIDPk):
    __tablename__ = "training_plans"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # TrainingPlanStatus: DRAFT | ACTIVE | PAUSED | COMPLETED | CANCELLED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True
    )
    # Program config, e.g. {"program_duration_weeks":4,"sessions_per_week":3,...}
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    piano_sessions: Mapped[list["PianoSession"]] = relationship(back_populates="training_plan")


class PianoSession(Base, UUIDPk):
    """One training round. Raw events live in piano_events and matter more
    than the summary scores stored here."""

    __tablename__ = "piano_sessions"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    training_plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("training_plans.id", ondelete="SET NULL"), nullable=True
    )

    # PianoMode: CALIBRATION | SINGLE_KEY_RHYTHM | ALTERNATING_HANDS |
    #            MAPPED_SEQUENCE | FOLLOW_THE_BEAT
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # InputSource: HUMAN_KEYBOARD | SYNTHETIC_SELFTEST | SEED_DEMO.
    # Provenance marker. A row whose events were not produced by a real person
    # must never be read as a measurement, so the value travels with the row and
    # is surfaced by the API. `SEED_DEMO` rows also carry randomised summary
    # values from scripts/seed_demo.py and are excluded from trends.
    input_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="HUMAN_KEYBOARD", server_default="HUMAN_KEYBOARD", index=True
    )

    # ---- difficulty parameters actually used for this round ----
    bpm: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    judgement_window_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    sequence_length: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    note_density: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    hand_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="SINGLE")
    weak_side_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    finger_complexity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    session_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    # ---- P0 session metrics ----
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    miss_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    mean_response_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_response_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_latency_cv: Mapped[float | None] = mapped_column(Float, nullable=True)

    mean_timing_error_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_timing_error_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    timing_mae_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    timing_error_cv: Mapped[float | None] = mapped_column(Float, nullable=True)

    early_press_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    late_press_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    left_mean_latency: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_mean_latency: Mapped[float | None] = mapped_column(Float, nullable=True)
    left_right_latency_difference: Mapped[float | None] = mapped_column(Float, nullable=True)

    left_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)

    weak_finger_error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sequence_completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ---- adaptive difficulty audit trail ----
    difficulty_before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reason produced by the rule engine (spec V2 section 23); kept for traceability.
    adaptation_reason_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metrics_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    training_plan: Mapped["TrainingPlan | None"] = relationship(back_populates="piano_sessions")
    events: Mapped[list["PianoEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PianoEvent(Base, UUIDPk):
    """Raw key event. Raw events take priority over any total score.

    response_latency_ms and timing_error_ms are strictly different quantities:
      response_latency_ms = first_valid_response_time - cue_onset_time
      timing_error_ms     = actual_time_ms - target_time_ms
    """

    __tablename__ = "piano_events"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("piano_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)

    cue_onset_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    response_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timing_error_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    key_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Hand: LEFT | RIGHT (task mapping, not observed anatomy)
    hand: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # FingerHint: THUMB | INDEX | MIDDLE | RING | LITTLE.
    # Task mapping only: a computer keyboard cannot reveal which physical finger
    # the patient actually used. Must be labelled as such in UI and reports.
    finger_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)

    key_down_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key_up_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hold_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    is_missed: Mapped[bool | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    session: Mapped["PianoSession"] = relationship(back_populates="events")


class PoseSession(Base, UUIDPk):
    """One ballet movement exercise attempt.

    Raw interpretable metrics are stored first (raw_metrics_json). The 0-100
    display scores may only be stored once their formulas are fixed and
    versioned in the exercise definition; until then they stay NULL.

    The exercise set started as five yoga poses and was replaced by five ballet
    exercises. Rows written before the change keep their original exercise_type
    and are still readable; `display_name()` in `app/ml/pose/exercises.py` maps
    the retired keys to a neutral label.
    """

    __tablename__ = "pose_sessions"

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # PoseExerciseType (the five ballet exercises; retired yoga keys may remain
    # on historical rows). 48 chars fits BALLET_SEATED_ALTERNATING_ARM_RAISE.
    exercise_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    difficulty_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ExecutionMode: SEATED | STANDING_SUPPORTED. Chosen by the doctor before the
    # task starts, because the patient should not have to judge which version of
    # an exercise they are safe to perform. Rows written before the column exist
    # are UNKNOWN rather than guessed: the same angles measured seated and
    # standing describe different tasks, and claiming one would be an invention.
    execution_mode: Mapped[str] = mapped_column(
        String(24), nullable=False, default="UNKNOWN", server_default="UNKNOWN", index=True
    )

    # InputSource: HUMAN_KEYBOARD | SYNTHETIC_SELFTEST | SEED_DEMO. Same
    # provenance rule as piano_sessions: a recording that is not a real patient
    # must never be read as a measurement (docs/metric_definitions.md 2.3.4).
    input_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="HUMAN_KEYBOARD",
        server_default="HUMAN_KEYBOARD", index=True,
    )

    # Display scores -- NULL until formulas are defined (spec V2 sections 28-30).
    completion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_of_motion: Mapped[float | None] = mapped_column(Float, nullable=True)
    symmetry_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    stability_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    hold_time_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    repetition_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movement_speed: Mapped[float | None] = mapped_column(Float, nullable=True)

    valid_pose_frame_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw interpretable metrics go here first.
    raw_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Per-recording quality report: frame counts, valid ratio, visibility, which
    # gates failed and why. Stored whether or not the analysis was accepted.
    quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    algorithm_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exercise_definition_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # The recording the analysis came from, when one was uploaded.
    media_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
