"""Tests for the piano training-recipe metrics.

These cover the metric layer only. The cue policies that feed it are tested on
the frontend (`frontend/tests/recipes.test.ts`), because that is where the cue
stream is generated; what matters here is that the backend reads the fields the
frontend writes and reports them without inventing anything.

The two rules worth stating plainly, because both are easy to get wrong and
neither is visible in the UI:

  * A bimanual pair where only one hand arrived has NO synchrony value. Reporting
    0 ms would claim perfect coordination for a press that never happened.

  * Once a CFT cue is withdrawn there is no cue onset, so the response latency for
    that beat is null. Timing error survives, because the beat is still defined.
    Averaging latency across both phases would describe a reaction to something
    the patient was never shown.
"""

from __future__ import annotations

from app.utils.piano_metrics import compute_metrics


def cued(
    *,
    index: int,
    correct: bool = True,
    timing: int | None = 0,
    latency: int | None = 700,
    hand: str = "LEFT",
    pair_role: str | None = None,
    sync: int | None = None,
    accent: bool | None = None,
    beat_in_bar: int | None = None,
) -> dict:
    """A cue row with an onset (an ordinary, cued beat)."""
    return {
        "event_index": index,
        "cue_index": index,
        "cue_onset_time_ms": 100 + index * 800,
        "target_time_ms": 800 + index * 800,
        "actual_time_ms": (800 + index * 800 + timing) if correct else None,
        "timing_error_ms": timing if correct else None,
        "response_latency_ms": latency if correct else None,
        "hand": hand,
        "pair_role": pair_role,
        "inter_hand_onset_diff_ms": sync,
        "is_accent": accent,
        "beat_in_bar": beat_in_bar,
        "is_correct": correct,
        "is_missed": not correct,
    }


def uncued(*, index: int, correct: bool = True, timing: int | None = 0) -> dict:
    """A cue row after the recipe withdrew the cue: onset null, target kept."""
    return {
        "event_index": index,
        "cue_index": index,
        "cue_onset_time_ms": None,
        "target_time_ms": 800 + index * 800,
        "actual_time_ms": (800 + index * 800 + timing) if correct else None,
        "timing_error_ms": timing if correct else None,
        "response_latency_ms": None,
        "hand": "RIGHT",
        "pair_role": None,
        "inter_hand_onset_diff_ms": None,
        "is_accent": None,
        "beat_in_bar": None,
        "is_correct": correct,
        "is_missed": not correct,
    }


# --------------------------------------------------------------- CFT split


def test_cft_reports_the_two_phases_separately():
    events = [
        cued(index=0, timing=10),
        cued(index=1, timing=30),
        uncued(index=2, timing=20),
        uncued(index=3, timing=60, correct=False),
    ]
    m = compute_metrics(events)

    assert m.cued_phase_accuracy == 1.0
    assert m.free_phase_accuracy == 0.5
    assert m.free_phase_cue_count == 2
    # Mean absolute error over the beats that were hit: |20| only.
    assert m.free_phase_timing_mae_ms == 20.0


def test_cft_latency_comes_only_from_the_cued_phase():
    events = [cued(index=0, latency=700), cued(index=1, latency=760), uncued(index=2), uncued(index=3)]
    m = compute_metrics(events)
    # 730 is the mean of the two cued latencies. The un-cued rows carry None, so
    # they cannot drag it down or be counted as instant reactions.
    assert m.mean_response_latency_ms == 730.0


def test_a_plain_round_reports_no_phase_split():
    events = [cued(index=0), cued(index=1), cued(index=2)]
    m = compute_metrics(events)
    assert m.cued_phase_accuracy is None
    assert m.free_phase_accuracy is None
    assert m.free_phase_cue_count is None


def test_free_phase_interval_cv_needs_at_least_two_intervals():
    # A real CFT round has both phases; the CV is over the un-cued hits only.
    # Three un-cued hits give two intervals, which is the floor for a spread
    # measure. Two hits give one interval and no CV.
    three = [cued(index=0), uncued(index=1), uncued(index=2), uncued(index=3)]
    assert compute_metrics(three).free_phase_interval_cv is not None

    two = [cued(index=0), uncued(index=1), uncued(index=2)]
    assert compute_metrics(two).free_phase_interval_cv is None


def test_a_round_with_no_cued_beats_reports_no_split():
    # Nothing to compare against: this is an un-cued-only stream, which is not a
    # phase split however many rows it has.
    events = [uncued(index=0), uncued(index=1), uncued(index=2)]
    m = compute_metrics(events)
    assert m.cued_phase_accuracy is None
    assert m.free_phase_accuracy is None


# ----------------------------------------------------------- bimanual sync


def test_bimanual_sync_averages_the_pairs():
    events = [
        cued(index=0, pair_role="PRIMARY", sync=40),
        cued(index=0, pair_role="SECONDARY", sync=40, hand="RIGHT"),
        cued(index=1, pair_role="PRIMARY", sync=20),
        cued(index=1, pair_role="SECONDARY", sync=20, hand="RIGHT"),
    ]
    m = compute_metrics(events)
    assert m.inter_hand_sync_mean_ms == 30.0
    assert m.inter_hand_sync_sd_ms == 10.0
    # The pair is counted once, not once per row.
    assert m.inter_hand_pair_count == 2


def test_a_missing_hand_produces_no_synchrony_value():
    events = [
        cued(index=0, pair_role="PRIMARY", sync=None),
        cued(index=0, pair_role="SECONDARY", sync=None, hand="RIGHT", correct=False),
    ]
    m = compute_metrics(events)
    # Not 0: the right hand never arrived, so there is nothing to compare.
    assert m.inter_hand_sync_mean_ms is None
    assert m.inter_hand_sync_sd_ms is None
    # The pair itself still exists, and it was not fully hit.
    assert m.inter_hand_pair_count == 1
    assert m.accuracy == 0.5


def test_single_key_rounds_report_no_synchrony():
    events = [cued(index=0), cued(index=1)]
    m = compute_metrics(events)
    assert m.inter_hand_sync_mean_ms is None
    assert m.inter_hand_pair_count is None


# --------------------------------------------------------------- accents


def test_accent_hit_rate_counts_beats_not_rows():
    # Two hands on one accented beat is ONE accent, and it was hit.
    events = [
        cued(index=0, accent=True, beat_in_bar=1, pair_role="PRIMARY"),
        cued(index=0, accent=True, beat_in_bar=1, pair_role="SECONDARY", hand="RIGHT"),
        cued(index=1, accent=False, beat_in_bar=2),
        cued(index=4, accent=True, beat_in_bar=1, correct=False),
    ]
    m = compute_metrics(events)
    assert m.accent_cue_count == 2, "two accented beats, not three rows"
    assert m.accent_hit_rate == 0.5


def test_a_half_hit_accent_beat_is_not_a_hit():
    events = [
        cued(index=0, accent=True, pair_role="PRIMARY", correct=True),
        cued(index=0, accent=True, pair_role="SECONDARY", hand="RIGHT", correct=False),
    ]
    m = compute_metrics(events)
    assert m.accent_cue_count == 1
    assert m.accent_hit_rate == 0.0


def test_non_accent_rounds_report_no_accent_metrics():
    events = [cued(index=0), cued(index=1)]
    m = compute_metrics(events)
    assert m.accent_hit_rate is None
    assert m.accent_cue_count is None


# ------------------------------------------------------- existing behaviour


def test_the_recipe_metrics_do_not_disturb_the_existing_ones():
    # A round with no recipe fields must produce exactly what it did before.
    events = [cued(index=0), cued(index=1, correct=False)]
    m = compute_metrics(events)
    assert m.total_cues == 2
    assert m.correct_count == 1
    assert m.missed_count == 1
    assert m.accuracy == 0.5
    assert m.miss_rate == 0.5
    assert m.mean_response_latency_ms == 700.0


def test_recipe_fields_never_appear_in_the_database_column_mapping():
    # The recipe metrics are stored in the session's audit blob, not as columns.
    # If one were mapped here it would need a migration that does not exist.
    events = [cued(index=0, pair_role="PRIMARY", sync=30, accent=True)]
    m = compute_metrics(events)
    fields = m.to_db_fields()
    for name in (
        "inter_hand_sync_mean_ms",
        "cued_phase_accuracy",
        "free_phase_timing_mae_ms",
        "accent_hit_rate",
    ):
        assert name not in fields
