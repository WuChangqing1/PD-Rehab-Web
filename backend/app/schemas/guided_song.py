from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Difficulty = Literal['BEGINNER','INTERMEDIATE','ADVANCED']


class GuidedSongCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    patient_id: str = Field(min_length=1, max_length=36)
    client_request_id: str = Field(min_length=1, max_length=128)
    song_id: Literal['two_tigers'] = 'two_tigers'
    song_version: Literal['1'] = '1'
    selected_hand: Literal['LEFT','RIGHT']
    initial_difficulty: Difficulty
    input_source: Literal['HUMAN_KEYBOARD','SYNTHETIC_SELFTEST'] = 'HUMAN_KEYBOARD'
    is_simulation: bool = False
    client_clock_origin_epoch_ms: int | None = Field(None,ge=0,le=100000000000000,strict=True)


class GuidedEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    seq: int = Field(ge=0, strict=True)
    type: Literal['CUE','DOWN','UP','SKIP','PAUSE','RESUME']
    segment_index: Literal[1,2]
    note_index: int = Field(ge=0, le=31, strict=True)
    time_ms: float = Field(ge=0, le=86400000, allow_inf_nan=False)
    midi: int | None = Field(default=None, ge=60, le=71)
    press_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode='after')
    def key_fields(self):
        if self.type in ('DOWN','UP') and (self.midi not in [60,62,64,65,67,69,71] or not self.press_id):
            raise ValueError('Key events require a seven-key midi and press_id')
        return self


class GuidedEvents(BaseModel):
    model_config = ConfigDict(extra='forbid')
    events: list[GuidedEvent] = Field(max_length=20000)


class EmotionStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: bool
    status: Literal['IDLE','CONSENT_REQUIRED','CONNECTING','MODEL_NOT_CONFIGURED','STREAMING','UNAVAILABLE','STOPPED','SIMULATED']
