"""Every field the client may post must actually be stored.

WHY THIS EXISTS
===============
`PianoEventIn` accepts fields that have no DB column: they travel in a side
channel inside the session's audit JSON, and `_event_dicts` rejoins them on read.
That design works, but it fails silently in one specific way -- a field can be
added to the request schema and never added to the side channel, in which case it
is accepted, dropped, and never seen again. Nothing raises.

That is exactly what happened here. `pair_role` and `inter_hand_onset_diff_ms`
were added to the schema for the bimanual recipe, the frontend sent them, Pydantic
validated them, and the service stored neither. A bimanual round then computed its
hand-synchrony metric from events that had lost their pairing and reported None.

These tests make the requirement explicit rather than relying on someone
remembering the side channel exists.
"""

from __future__ import annotations

from app.schemas.piano import PianoEventIn
from app.services.piano_service import (
    EVENT_EXTRA_FIELDS,
    PIANO_EVENT_COLUMNS,
)

# Fields backed by a real column on piano_events.
COLUMN_BACKED = set(PIANO_EVENT_COLUMNS)


def test_the_column_list_is_not_empty_and_looks_right():
    # A guard on the introspection itself: if the import silently returned an
    # empty set, every test below would pass for the wrong reason.
    assert len(COLUMN_BACKED) >= 15, f"only found {len(COLUMN_BACKED)} piano_events columns"
    for expected in ("event_index", "target_time_ms", "is_correct", "hand"):
        assert expected in COLUMN_BACKED, f"{expected} is not recognised as a column"


def test_every_schema_field_is_stored_somewhere():
    declared = set(PianoEventIn.model_fields)
    stored = COLUMN_BACKED | set(EVENT_EXTRA_FIELDS)

    missing = sorted(declared - stored)
    assert missing == [], (
        "these fields are accepted by the API but stored nowhere, so they are "
        f"silently dropped: {missing}"
    )


def test_the_recipe_fields_are_all_stored():
    # The specific regression, named.
    for field in (
        "recipe_id",
        "pair_role",
        "inter_hand_onset_diff_ms",
        "beat_in_bar",
        "is_accent",
    ):
        assert field in PianoEventIn.model_fields, f"{field} is not accepted by the API"
        assert field in EVENT_EXTRA_FIELDS, f"{field} would be dropped on save"


def test_the_side_channel_does_not_claim_column_backed_fields():
    # A field listed in both places would be written twice and could disagree.
    overlap = sorted(set(EVENT_EXTRA_FIELDS) & COLUMN_BACKED)
    assert overlap == [], f"these are stored twice: {overlap}"


def test_the_original_extra_fields_are_still_listed():
    # The side channel predates this change; its existing members must survive.
    for field in ("is_wrong_key", "cue_index", "sequence_position", "sequence_length"):
        assert field in EVENT_EXTRA_FIELDS, f"{field} was removed from the side channel"
