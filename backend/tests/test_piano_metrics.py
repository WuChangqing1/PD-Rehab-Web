"""Piano session metric tests.

Ground truth is arithmetic, not the implementation: events are constructed with
known latencies and timing errors so the expected metrics can be worked out by
hand. The distinction between response_latency and timing_error is asserted
explicitly, because conflating them is the single most damaging mistake this
module could make.
"""

from __future__ import annotations

import pytest

from app.utils.piano_metrics import compute_metrics, validation_warnings


def cue_event(
    index: int,
    *,
    cue_onset: int,
    target: int,
    actual: int | None,
    hand: str = "LEFT",
    finger: str = "INDEX",
    correct: bool = True,
    missed: bool = False,
) -> dict:
    """Build a cue row. latency is from cue onset, error is from the target."""
    return {
        "event_index": index,
        "cue_onset_time_ms": cue_onset,
        "target_time_ms": target,
        "actual_time_ms": actual,
        "response_latency_ms": None if actual is None else actual - cue_onset,
        "timing_error_ms": None if actual is None else actual - target,
        "key_code": "KeyZ",
        "note": "C3",
        "hand": hand,
        "finger_hint": finger,
        "key_down_time_ms": actual,
        "key_up_time_ms": None if actual is None else actual + 120,
        "hold_duration_ms": None if actual is None else 120,
        "is_correct": correct,
        "is_missed": missed,
        "is_wrong_key": False,
        "cue_index": index,
    }


def wrong_event(index: int, *, cue_onset: int, target: int, actual: int, hand="LEFT") -> dict:
    return {
        "event_index": index,
        "cue_onset_time_ms": cue_onset,
        "target_time_ms": target,
        "actual_time_ms": actual,
        "response_latency_ms": None,
        "timing_error_ms": actual - target,
        "key_code": "KeyX",
        "note": "D3",
        "hand": hand,
        "finger_hint": "RING",
        "key_down_time_ms": actual,
        "key_up_time_ms": actual + 80,
        "hold_duration_ms": 80,
        "is_correct": False,
        "is_missed": False,
        "is_wrong_key": True,
        "cue_index": index,
    }


# ------------------------------------------------------------ latency vs error
def test_latency_and_timing_error_are_different_quantities():
    """A cue where the patient responds quickly but off the beat.

    cue at 0, target at 700, press at 760:
        latency = 760 - 0   = 760 ms   (slow to respond)
        error   = 760 - 700 =  60 ms   (only slightly late)
    """
    events = [cue_event(0, cue_onset=0, target=700, actual=760)]
    m = compute_metrics(events)
    assert m.mean_response_latency_ms == pytest.approx(760.0)
    assert m.mean_timing_error_ms == pytest.approx(60.0)

    # And the mirror case: responds immediately, but far from the beat.
    fast_but_early = [cue_event(0, cue_onset=0, target=700, actual=300)]
    m2 = compute_metrics(fast_but_early)
    assert m2.mean_response_latency_ms == pytest.approx(300.0)
    assert m2.mean_timing_error_ms == pytest.approx(-400.0)


def test_latency_is_not_derived_from_target():
    """Latency must never be computed against the target time."""
    events = [cue_event(0, cue_onset=500, target=1200, actual=1300)]
    m = compute_metrics(events)
    assert m.mean_response_latency_ms == pytest.approx(800.0)  # 1300 - 500
    assert m.mean_timing_error_ms == pytest.approx(100.0)  # 1300 - 1200


# ------------------------------------------------------------------- accuracy
def test_accuracy_and_miss_rate():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700),
        cue_event(1, cue_onset=1000, target=1700, actual=1700),
        cue_event(2, cue_onset=2000, target=2700, actual=2700),
        cue_event(3, cue_onset=3000, target=3700, actual=3600),  # 100 ms early
        cue_event(4, cue_onset=4000, target=4700, actual=None, correct=False, missed=True),
    ]
    m = compute_metrics(events)
    assert m.total_cues == 5
    assert m.correct_count == 4
    assert m.missed_count == 1
    assert m.accuracy == pytest.approx(0.8)
    assert m.miss_rate == pytest.approx(0.2)


def test_wrong_presses_do_not_inflate_the_cue_count():
    """Wrong-key presses are error rows, not extra targets."""
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700),
        wrong_event(1, cue_onset=1000, target=1700, actual=1750),
        cue_event(1, cue_onset=1000, target=1700, actual=1800),
    ]
    m = compute_metrics(events)
    assert m.total_cues == 2
    assert m.wrong_count == 1
    assert m.correct_count == 2
    assert m.accuracy == pytest.approx(1.0)


def test_no_events_yields_no_metrics():
    m = compute_metrics([])
    assert m.total_cues == 0
    assert m.accuracy is None
    assert m.miss_rate is None
    assert m.mean_response_latency_ms is None
    assert m.mean_timing_error_ms is None


# ------------------------------------------------------------------------ CV
def test_response_latency_cv_matches_manual_computation():
    # latencies 400, 500, 600 -> mean 500, population std 81.6497, cv 0.1633
    events = [
        cue_event(0, cue_onset=0, target=700, actual=400),
        cue_event(1, cue_onset=0, target=700, actual=500),
        cue_event(2, cue_onset=0, target=700, actual=600),
    ]
    m = compute_metrics(events)
    assert m.response_latency_cv == pytest.approx(81.649658 / 500.0, rel=1e-5)


def test_timing_error_cv_is_null_when_mean_is_near_zero():
    """Early and late presses cancel out; CV is undefined, not infinite."""
    events = [
        cue_event(0, cue_onset=0, target=1000, actual=900),  # -100
        cue_event(1, cue_onset=0, target=1000, actual=1100),  # +100
    ]
    m = compute_metrics(events)
    assert m.mean_timing_error_ms == pytest.approx(0.0)
    assert m.timing_error_cv is None
    # an honest alternative is provided
    assert m.timing_error_std_ms == pytest.approx(100.0)
    assert m.timing_error_cv_note is not None


def test_never_returns_nan_or_infinity():
    cases = [
        [],
        [cue_event(0, cue_onset=0, target=0, actual=0)],
        [cue_event(0, cue_onset=0, target=1000, actual=1000)] * 2,
        [cue_event(i, cue_onset=0, target=0, actual=0) for i in range(5)],
    ]
    for events in cases:
        m = compute_metrics(events)
        for key, value in m.to_dict().items():
            if isinstance(value, float):
                assert value == value, f"{key} is NaN"
                assert abs(value) != float("inf"), f"{key} is infinite"


# --------------------------------------------------------------- statistics
def test_median_and_mean_timing_error():
    errors = [-200, -100, 0, 100, 400]
    events = [
        cue_event(i, cue_onset=0, target=1000, actual=1000 + err)
        for i, err in enumerate(errors)
    ]
    m = compute_metrics(events)
    assert m.mean_timing_error_ms == pytest.approx(40.0)  # 200/5
    assert m.median_timing_error_ms == pytest.approx(0.0)
    assert m.mean_absolute_timing_error_ms == pytest.approx((200 + 100 + 0 + 100 + 400) / 5)


def test_early_and_late_rates():
    # median absolute error is 100, so the threshold is 100
    errors = [-300, -50, 0, 50, 300]
    events = [
        cue_event(i, cue_onset=0, target=1000, actual=1000 + err)
        for i, err in enumerate(errors)
    ]
    m = compute_metrics(events)
    assert m.early_press_rate == pytest.approx(1 / 5)  # only -300 is < -100
    assert m.late_press_rate == pytest.approx(1 / 5)  # only +300 is > 100


def test_error_streak_max():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700),  # correct
        cue_event(1, cue_onset=1000, target=1700, actual=None, correct=False, missed=True),
        cue_event(2, cue_onset=2000, target=2700, actual=None, correct=False, missed=True),
        cue_event(3, cue_onset=3000, target=3700, actual=None, correct=False, missed=True),
        cue_event(4, cue_onset=4000, target=4700, actual=4700),  # correct
        cue_event(5, cue_onset=5000, target=5700, actual=None, correct=False, missed=True),
    ]
    m = compute_metrics(events)
    assert m.error_streak_max == 3


def test_hold_duration_mean():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700),
        cue_event(1, cue_onset=1000, target=1700, actual=1700),
    ]
    m = compute_metrics(events)
    assert m.key_hold_duration_ms == pytest.approx(120.0)


# --------------------------------------------------------------- left/right
def test_left_right_latency_difference_is_left_minus_right():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=600, hand="LEFT"),  # 600
        cue_event(1, cue_onset=0, target=700, actual=600, hand="LEFT"),  # 600
        cue_event(2, cue_onset=0, target=700, actual=400, hand="RIGHT"),  # 400
        cue_event(3, cue_onset=0, target=700, actual=400, hand="RIGHT"),  # 400
    ]
    m = compute_metrics(events)
    assert m.left_mean_latency == pytest.approx(600.0)
    assert m.right_mean_latency == pytest.approx(400.0)
    assert m.left_right_latency_difference == pytest.approx(200.0)


def test_missing_side_leaves_difference_null_not_zero():
    events = [cue_event(0, cue_onset=0, target=700, actual=600, hand="LEFT")]
    m = compute_metrics(events)
    assert m.left_mean_latency == pytest.approx(600.0)
    assert m.right_mean_latency is None
    assert m.left_right_latency_difference is None


def test_per_hand_accuracy():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700, hand="LEFT"),
        cue_event(1, cue_onset=0, target=700, actual=None, correct=False, missed=True, hand="LEFT"),
        cue_event(2, cue_onset=0, target=700, actual=700, hand="RIGHT"),
        cue_event(3, cue_onset=0, target=700, actual=700, hand="RIGHT"),
    ]
    m = compute_metrics(events)
    assert m.left_accuracy == pytest.approx(0.5)
    assert m.right_accuracy == pytest.approx(1.0)


# ------------------------------------------------------------- weak finger
def test_weak_finger_error_rate_counts_only_ring_and_little():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700, finger="RING"),
        cue_event(1, cue_onset=0, target=700, actual=None, correct=False, missed=True, finger="RING"),
        cue_event(2, cue_onset=0, target=700, actual=None, correct=False, missed=True, finger="LITTLE"),
        cue_event(3, cue_onset=0, target=700, actual=700, finger="INDEX"),
        cue_event(4, cue_onset=0, target=700, actual=None, correct=False, missed=True, finger="INDEX"),
    ]
    m = compute_metrics(events)
    # 2 of 3 weak-finger cues were errors; the INDEX miss must not count
    assert m.weak_finger_error_rate == pytest.approx(2 / 3)


def test_weak_finger_rate_null_when_no_weak_cues():
    events = [cue_event(0, cue_onset=0, target=700, actual=700, finger="INDEX")]
    m = compute_metrics(events)
    assert m.weak_finger_error_rate is None


# ------------------------------------------------------------ completion
def test_session_completion_rate():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700),
        cue_event(1, cue_onset=0, target=700, actual=700),
    ]
    assert compute_metrics(events, planned_cues=4).session_completion_rate == pytest.approx(0.5)
    assert compute_metrics(events, planned_cues=2).session_completion_rate == pytest.approx(1.0)
    # no plan given: falls back to the observed cue count
    assert compute_metrics(events).session_completion_rate == pytest.approx(1.0)


def test_sequence_completion_rate():
    a = cue_event(0, cue_onset=0, target=700, actual=700)
    a.update(sequence_position=1, sequence_length=3, cue_index=0)
    b = cue_event(1, cue_onset=400, target=1100, actual=1100)
    b.update(sequence_position=2, sequence_length=3, cue_index=0)
    c = cue_event(2, cue_onset=800, target=1500, actual=None, correct=False, missed=True)
    c.update(sequence_position=3, sequence_length=3, cue_index=0)

    d = cue_event(3, cue_onset=2000, target=2700, actual=2700)
    d.update(sequence_position=1, sequence_length=3, cue_index=3)
    e = cue_event(4, cue_onset=2400, target=3100, actual=3100)
    e.update(sequence_position=2, sequence_length=3, cue_index=3)
    f = cue_event(5, cue_onset=2800, target=3500, actual=3500)
    f.update(sequence_position=3, sequence_length=3, cue_index=3)

    m = compute_metrics([a, b, c, d, e, f])
    assert m.sequence_completion_rate == pytest.approx(0.5)  # first group incomplete


# ------------------------------------------------------------- validation
def test_validation_flags_inconsistent_latency():
    events = [cue_event(0, cue_onset=0, target=700, actual=700)]
    events[0]["response_latency_ms"] = 999  # deliberately wrong
    warnings = validation_warnings(compute_metrics(events), events)
    assert any("response_latency_ms" in w for w in warnings)


def test_validation_flags_inconsistent_timing_error():
    events = [cue_event(0, cue_onset=0, target=700, actual=700)]
    events[0]["timing_error_ms"] = -999
    warnings = validation_warnings(compute_metrics(events), events)
    assert any("timing_error_ms" in w for w in warnings)


def test_validation_flags_missing_cue_onset():
    events = [cue_event(0, cue_onset=0, target=700, actual=700)]
    events[0]["cue_onset_time_ms"] = None
    events[0]["response_latency_ms"] = None
    warnings = validation_warnings(compute_metrics(events), events)
    assert any("cue_onset_time_ms" in w for w in warnings)


def test_validation_clean_on_well_formed_events():
    events = [
        cue_event(0, cue_onset=0, target=700, actual=700),
        cue_event(1, cue_onset=1000, target=1700, actual=1750),
    ]
    warnings = validation_warnings(compute_metrics(events), events)
    assert warnings == []


def test_validation_flags_implausible_latency():
    events = [cue_event(0, cue_onset=0, target=700, actual=9000)]
    warnings = validation_warnings(compute_metrics(events), events)
    assert any("3 秒" in w for w in warnings)


# ------------------------------------------------------- database field map
def test_to_db_fields_matches_piano_sessions_columns():
    """The mapping must cover exactly the metric columns on piano_sessions."""
    from app.db.models import PianoSession

    columns = {c.name for c in PianoSession.__table__.columns}
    mapped = set(compute_metrics([]).to_db_fields())
    missing = mapped - columns
    assert not missing, f"mapped fields with no column: {sorted(missing)}"
    for required in (
        "accuracy",
        "miss_rate",
        "mean_response_latency_ms",
        "median_response_latency_ms",
        "response_latency_cv",
        "mean_timing_error_ms",
        "median_timing_error_ms",
        "timing_mae_ms",
        "timing_error_cv",
        "left_mean_latency",
        "right_mean_latency",
        "left_right_latency_difference",
        "left_accuracy",
        "right_accuracy",
        "weak_finger_error_rate",
        "session_completion_rate",
    ):
        assert required in mapped, f"{required} is not mapped to a column"
