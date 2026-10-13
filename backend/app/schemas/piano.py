"""Piano training schemas (spec V2 sections 17, 18, 20, 43, 44).

Raw events are accepted in full, including fields the database stores inside a
JSON column rather than as dedicated columns (wrong-key flag, sequence position).
Nothing is dropped on the way in, so a session can be re-analysed later.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import JsonText, ORMModel

PianoModeLiteral = Literal[
    "CALIBRATION",
    "SINGLE_KEY_RHYTHM",
    "ALTERNATING_HANDS",
    "MAPPED_SEQUENCE",
    "FOLLOW_THE_BEAT",
    # Optional extra: the patient watches a short sequence, then reproduces it.
    # Training, not a cognitive assessment, and never a required round.
    "MEMORY_RHYTHM",
]
HandLiteral = Literal["LEFT", "RIGHT"]
FingerLiteral = Literal["THUMB", "INDEX", "MIDDLE", "RING", "LITTLE"]
# Training recipes (docs/05). Each is a template over one of the modes above, so
# it never replaces `mode` -- it names the practice the round belonged to.
RecipeIdLiteral = Literal[
    "SFT_CUE_SYNC",
    "CFT_RHYTHM_HOLD",
    "BIMANUAL_SYNC",
    "ACCENT_GROUPING",
    "TEMPO_RAMP",
    "HOLD_RELEASE",
    "BIMANUAL_OFFSET",
    "REVERSE_SEQUENCE",
    "GO_NO_GO",
]
NEW_RECIPE_BASE_MODES = {
    "TEMPO_RAMP": "SINGLE_KEY_RHYTHM",
    "HOLD_RELEASE": "SINGLE_KEY_RHYTHM",
    "BIMANUAL_OFFSET": "SINGLE_KEY_RHYTHM",
    "REVERSE_SEQUENCE": "MEMORY_RHYTHM",
    "GO_NO_GO": "SINGLE_KEY_RHYTHM",
}
# Where the key events came from. Anything other than HUMAN_KEYBOARD means the
# row is not a human measurement and must be labelled as such wherever it shows.
InputSourceLiteral = Literal["HUMAN_KEYBOARD", "SYNTHETIC_SELFTEST", "SEED_DEMO"]


class DifficultyConfigSchema(BaseModel):
    """The difficulty parameters actually used for a round."""

    bpm: int = Field(60, ge=20, le=300)
    judgement_window_ms: int = Field(300, ge=50, le=2000)
    sequence_length: int = Field(4, ge=1, le=12)
    note_density: float = Field(1.0, ge=0.25, le=4.0)
    hand_mode: Literal["SINGLE", "ALTERNATING", "BOTH"] = "SINGLE"
    weak_side_ratio: float = Field(0.5, ge=0.0, le=1.0)
    finger_complexity: int = Field(1, ge=1, le=3)
    session_duration_sec: int = Field(60, ge=10, le=900)
    tempo_ceiling_bpm: float | None = Field(None, ge=40, le=160, allow_inf_nan=False)


class PianoEventIn(BaseModel):
    """One raw key event.

    `cue_onset_time_ms` and `target_time_ms` are required because they are what
    makes `response_latency_ms` and `timing_error_ms` interpretable; the backend
    does not recompute them from wall-clock time.
    """

    event_index: int = Field(..., ge=0)
    cue_onset_time_ms: int | None = None
    target_time_ms: int | None = None
    actual_time_ms: int | None = None
    response_latency_ms: int | None = None
    timing_error_ms: int | None = None

    key_code: str | None = Field(None, max_length=32)
    note: str | None = Field(None, max_length=16)
    hand: HandLiteral | None = None
    finger_hint: FingerLiteral | None = None

    key_down_time_ms: int | None = None
    key_up_time_ms: int | None = None
    hold_duration_ms: int | None = None

    is_correct: bool
    is_missed: bool

    # Stored inside the event JSON column, not as separate DB columns.
    is_wrong_key: bool = False
    cue_index: int | None = None
    sequence_position: int | None = None
    sequence_length: int | None = None

    # Memory-rhythm mode only. A demonstration note is played and highlighted for
    # the patient rather than asked of them, so it must be excluded from every
    # accuracy denominator: counting a cue nobody was allowed to answer as a miss
    # would report a failure that did not happen.
    is_prompt: bool = False
    memory_group: int | None = None

    # ---------------------------------------------------------- recipe fields
    # Absent on rows from the original five modes, so an older client keeps
    # working unchanged. Stored in the event JSON column, not as DB columns.
    #
    # `recipe_id` names the training template the round ran under (docs/05).
    # `inter_hand_onset_diff_ms` is the absolute gap between the two hands of a
    # bimanual cue, written on both rows of the pair. It is null when only one
    # hand arrived: a missing half is a miss, and reporting it as 0 ms would
    # claim perfect synchrony for a press that never happened.
    recipe_id: RecipeIdLiteral | None = None
    inter_hand_onset_diff_ms: int | None = Field(None, ge=0)
    pair_role: Literal["PRIMARY", "SECONDARY"] | None = None
    beat_in_bar: int | None = Field(None, ge=1, le=32)
    is_accent: bool | None = None
    tempo_segment: int | None = Field(None, ge=0, le=3)
    target_hold_ms: int | None = Field(None, ge=1)
    pair_id: int | None = Field(None, ge=0)
    target_offset_ms: int | None = Field(None, ge=0)
    cue_type: Literal["GO", "NO_GO"] | None = None

    @field_validator("hold_duration_ms")
    @classmethod
    def _hold_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("hold_duration_ms 不能为负数")
        return v


class PianoStartTime(BaseModel):
    # The frontend creates the DB record on save, after collection has started.
    # Older clients omit this and retain the server's creation time.
    started_at: datetime | None = None
    client_request_id: str | None = Field(None, min_length=1, max_length=64)

    @field_validator("started_at")
    @classmethod
    def _validate_started_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at requires a timezone")
        if value > datetime.now(timezone.utc) + timedelta(seconds=5):
            raise ValueError("started_at cannot be in the future")
        return value.astimezone(timezone.utc)


class PianoSessionCreate(PianoStartTime):
    """Open a training round. Returns the configuration the frontend must use."""

    mode: PianoModeLiteral
    # Training recipe this round belongs to (docs/05), or null for a plain mode.
    # A recipe is a template over `mode`, so both are recorded: `mode` says which
    # cue generator ran, `recipe_id` says which practice the round was.
    recipe_id: RecipeIdLiteral | None = None
    # Calibration is round 0 by convention; training rounds are 1..3.
    round_number: int = Field(0, ge=0, le=20)
    training_plan_id: str | None = None
    difficulty: DifficultyConfigSchema = Field(default_factory=DifficultyConfigSchema)
    # Seed makes the cue sequence reproducible from stored configuration.
    seed: int | None = None
    weak_hand: HandLiteral | None = None
    # Declared by the client. A scripted self-test must not be able to write a
    # row that later reads as a patient measurement.
    input_source: InputSourceLiteral = "HUMAN_KEYBOARD"

    @model_validator(mode="after")
    def _new_recipe_mode(self):
        expected = NEW_RECIPE_BASE_MODES.get(self.recipe_id)
        if expected is not None and self.mode != expected:
            raise ValueError(f"{self.recipe_id} requires {expected}")
        return self


class SpontaneousTapping(BaseModel):
    """The patient's own rhythm, measured with no cue present.

    A measurement, not a task: nothing here is scored right or wrong. It is what
    "110% of baseline tempo" is a percentage OF (see
    docs/piano_training_plan.md P1).
    """

    window_ms: int = Field(..., ge=0)
    tap_count: int = Field(..., ge=0)
    interval_ms: float | None = None
    rate_hz: float | None = None
    interval_cv: float | None = None
    note: str | None = None


class PianoRawPress(BaseModel):
    """Every captured press, including prompt-phase and extra input.

    Times are relative to the round start, separate from scored cue rows.
    """
    key_code: str = Field(..., min_length=1, max_length=32)
    midi: int = Field(..., ge=0, le=127)
    key_down_time_ms: float = Field(..., ge=0, allow_inf_nan=False)
    key_up_time_ms: float | None = Field(None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _release_follows_press(self):
        if self.key_up_time_ms is not None and self.key_up_time_ms < self.key_down_time_ms:
            raise ValueError("key_up_time_ms must follow key_down_time_ms")
        return self


class PianoEventsBatch(BaseModel):
    """Raw events for a round, posted in one batch.

    Raw events are the primary record: they are stored before any summary metric
    is considered, so the metrics can always be recomputed from them.
    """

    events: list[PianoEventIn] = Field(..., min_length=1, max_length=5000)
    planned_cues: int | None = Field(None, ge=0)
    # Client-computed metrics, kept for display. The server recomputes the
    # authoritative values from the events and stores both.
    client_metrics: dict[str, Any] | None = None
    input_latency_note: str | None = None
    # Calibration only. Optional and additive: it lands in the session audit JSON
    # and becomes part of the calibration baseline, so no migration is involved
    # and sessions recorded before it simply have no value.
    spontaneous_tapping: SpontaneousTapping | None = None
    raw_presses: list[PianoRawPress] | None = Field(None, max_length=5000)


class PianoCompleteRequest(BaseModel):
    """Close the round and record the adaptation decision."""

    difficulty_after: DifficultyConfigSchema | None = None
    adaptation: dict[str, Any] | None = None
    metrics_version: str | None = None
    interrupted: bool = False


class PianoEventRead(BaseModel):
    """A raw event as returned to the frontend.

    `is_wrong_key`, `cue_index` and the sequence fields are not dedicated DB
    columns; they are persisted in the session's audit JSON and re-joined here so
    the frontend can render wrong-key presses and replay a sequence exactly.
    """

    id: str | None = None
    session_id: str | None = None
    event_index: int
    cue_onset_time_ms: int | None
    target_time_ms: int | None
    actual_time_ms: int | None
    response_latency_ms: int | None
    timing_error_ms: int | None
    key_code: str | None
    note: str | None
    hand: str | None
    finger_hint: str | None
    key_down_time_ms: int | None
    key_up_time_ms: int | None
    hold_duration_ms: int | None
    is_correct: bool | None
    is_missed: bool | None
    is_wrong_key: bool = False
    cue_index: int | None = None
    sequence_position: int | None = None
    sequence_length: int | None = None
    is_prompt: bool = False
    memory_group: int | None = None
    recipe_id: str | None = None
    inter_hand_onset_diff_ms: int | None = None
    pair_role: Literal["PRIMARY", "SECONDARY"] | None = None
    beat_in_bar: int | None = None
    is_accent: bool | None = None
    tempo_segment: int | None = None
    target_hold_ms: int | None = None
    pair_id: int | None = None
    target_offset_ms: int | None = None
    cue_type: Literal["GO", "NO_GO"] | None = None
    created_at: datetime | None = None


class PianoSessionRead(ORMModel):
    id: str
    patient_id: str
    training_plan_id: str | None
    mode: str
    # Null for rounds run on a plain mode and for every row recorded before
    # recipes existed. A reader must treat null as "not a recipe round", never as
    # a missing value to be filled in.
    recipe_id: str | None
    round_number: int
    input_source: str

    bpm: int
    judgement_window_ms: int
    sequence_length: int
    note_density: float
    hand_mode: str
    weak_side_ratio: float
    finger_complexity: int
    session_duration_sec: int

    accuracy: float | None
    miss_rate: float | None
    mean_response_latency_ms: float | None
    median_response_latency_ms: float | None
    response_latency_cv: float | None
    mean_timing_error_ms: float | None
    median_timing_error_ms: float | None
    timing_mae_ms: float | None
    timing_error_cv: float | None
    early_press_rate: float | None
    late_press_rate: float | None
    left_mean_latency: float | None
    right_mean_latency: float | None
    left_right_latency_difference: float | None
    left_accuracy: float | None
    right_accuracy: float | None
    weak_finger_error_rate: float | None
    sequence_completion_rate: float | None
    session_completion_rate: float | None

    difficulty_before_json: JsonText = None
    difficulty_after_json: JsonText = None
    adaptation_reason_json: JsonText = None
    difficulty_engine_version: str | None
    metrics_version: str | None

    started_at: datetime | None
    completed_at: datetime | None


class PianoSessionDetail(PianoSessionRead):
    events: list[PianoEventRead] = Field(default_factory=list)
    planned_cues: int | None = None


class PianoCalibrationRequest(PianoStartTime):
    """Open a calibration round (30-60 s) used to set the personal baseline."""

    duration_sec: int = Field(45, ge=30, le=60)
    difficulty: DifficultyConfigSchema = Field(default_factory=DifficultyConfigSchema)
    input_source: InputSourceLiteral = "HUMAN_KEYBOARD"


class CalibrationBaselineRead(BaseModel):
    id: str
    patient_id: str
    baseline_accuracy: float | None
    baseline_response_latency: float | None
    baseline_response_latency_cv: float | None
    baseline_timing_mae: float | None
    baseline_left_accuracy: float | None
    baseline_right_accuracy: float | None
    baseline_left_latency: float | None
    baseline_right_latency: float | None
    # Measured in the uncued segment of calibration; null when not measured.
    # This is what a tempo percentage is taken of (docs/piano_training_plan.md P1).
    baseline_spontaneous_bpm: float | None = None
    baseline_spontaneous_interval_ms: float | None = None
    baseline_spontaneous_interval_cv: float | None = None
    calibration_version: str | None = None
    created_at: datetime
    algorithm_version: str | None = None
    is_active: bool = True
    snapshot: dict[str, Any] | None = None
