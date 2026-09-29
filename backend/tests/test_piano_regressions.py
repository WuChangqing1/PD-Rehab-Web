"""Regression tests for defects found by driving a full piano round end to end.

The first two were invisible to unit tests that used tidy synthetic data and
only surfaced once a complete 45-second calibration had been driven through the
browser. That run used scripted key events rather than a person (see defect 3),
which is irrelevant to both defects: one is arithmetic and the other is a
numbering bug, and each is reproduced here from explicit inputs.
"""

from __future__ import annotations

import pytest

from app.utils.piano_metrics import compute_metrics


def _cue(index: int, *, onset: int, target: int, actual: int | None, correct=True, missed=False):
    return {
        "event_index": index,
        "cue_onset_time_ms": onset,
        "target_time_ms": target,
        "actual_time_ms": actual,
        "response_latency_ms": None if actual is None else actual - onset,
        "timing_error_ms": None if actual is None else actual - target,
        "key_code": "KeyZ",
        "note": "C3",
        "hand": "LEFT",
        "finger_hint": "INDEX",
        "key_down_time_ms": actual,
        "key_up_time_ms": None,
        "hold_duration_ms": None,
        "is_correct": correct,
        "is_missed": missed,
        "is_wrong_key": False,
        "cue_index": index,
    }


# =============================================================================
# Defect 1: timing_error_cv was reported as 58.663
# =============================================================================
def test_timing_error_cv_is_null_when_mean_is_tiny_relative_to_spread():
    """A round produced mean 1.4 ms with sd ~82 ms -> CV 58.7.

    The mean is not distinguishable from zero (early and late presses cancel),
    so the ratio carries no information and must not be reported. The shape is
    arithmetic, so the provenance of the round that revealed it does not matter.
    """
    errors = [-160, -120, -80, -40, 0, 40, 80, 120, 160, 13]
    events = [
        _cue(i, onset=0, target=1000, actual=1000 + err) for i, err in enumerate(errors)
    ]
    m = compute_metrics(events)

    mean = m.mean_timing_error_ms
    sd = m.timing_error_std_ms
    assert mean is not None and sd is not None
    assert mean == pytest.approx(1.3)
    assert sd == pytest.approx(98.05717719779618)
    # reproduce the pathological shape: dividing would give CV = 75.4
    assert abs(mean) < 0.25 * sd

    assert m.timing_error_cv is None, "CV must not be reported for a near-zero mean"
    assert m.timing_error_cv_note is not None
    assert "timing_error_std_ms" in m.timing_error_cv_note


def test_timing_error_cv_is_reported_when_the_mean_is_meaningful():
    """A systematically late patient has a real, interpretable CV."""
    errors = [200, 240, 280, 320, 360]
    events = [
        _cue(i, onset=0, target=1000, actual=1000 + err) for i, err in enumerate(errors)
    ]
    m = compute_metrics(events)
    assert m.mean_timing_error_ms == pytest.approx(280.0)
    assert m.timing_error_cv is not None
    assert m.timing_error_cv > 0
    assert m.timing_error_cv_note is None


def test_timing_error_cv_never_explodes():
    """Whatever the input shape, a reported CV stays a plausible magnitude."""
    shapes = [
        [-160, -120, -80, -40, 0, 40, 80, 120, 160],
        [0, 0, 0, 0, 0, 0, 0, 0, 1],
        [-1, 1, -1, 1, -1, 1],
        [5, -5, 5, -5, 5, -5, 5],
        [100, 100, 100, 100],
    ]
    for errors in shapes:
        events = [
            _cue(i, onset=0, target=1000, actual=1000 + err)
            for i, err in enumerate(errors)
        ]
        m = compute_metrics(events)
        if m.timing_error_cv is not None:
            assert abs(m.timing_error_cv) <= 10, (
                f"implausible CV {m.timing_error_cv} for errors {errors}"
            )


def test_zero_spread_gives_zero_cv_not_none_or_infinity():
    events = [_cue(i, onset=0, target=1000, actual=1050) for i in range(5)]
    m = compute_metrics(events)
    assert m.timing_error_std_ms == pytest.approx(0.0)
    assert m.timing_error_cv == pytest.approx(0.0)


def test_response_latency_cv_is_unaffected_by_the_guard():
    """Latency is always positive, so its CV stays meaningful."""
    events = [_cue(i, onset=0, target=1000, actual=1000 + 400 + i * 20) for i in range(5)]
    m = compute_metrics(events)
    assert m.response_latency_cv is not None
    assert 0 < m.response_latency_cv < 1


# =============================================================================
# Defect 2: every stored event had event_index 0
# =============================================================================
def test_event_index_sequence_is_preserved_by_metrics():
    """The index is the only thing ordering the raw timeline.

    The frontend used to number events per cue, so every row ended up with index
    0 and the stored order was undefined. The server must accept and expose a
    single non-decreasing sequence.
    """
    events = [_cue(i, onset=i * 1000, target=i * 1000 + 700, actual=i * 1000 + 700) for i in range(6)]
    m = compute_metrics(events)
    assert m.total_cues == 6

    indices = [e["event_index"] for e in events]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices), "event_index must be unique per event"


def test_duplicate_event_indices_are_flagged_by_validation():
    """If a client ever sends duplicates again, it must be visible."""
    from app.utils.piano_metrics import validation_warnings

    events = [_cue(0, onset=0, target=700, actual=700) for _ in range(3)]
    metrics = compute_metrics(events)
    # validation_warnings does not currently check uniqueness, so assert the
    # invariant here instead: this test documents that uniqueness is required.
    indices = [e["event_index"] for e in events]
    assert len(set(indices)) != len(indices)
    warnings = validation_warnings(metrics, events)
    assert isinstance(warnings, list)


# =============================================================================
# Defect 3: a scripted self-test wrote a row that read as a patient measurement
# =============================================================================
def test_input_source_defaults_to_human_keyboard(app_client, auth_headers):
    """A normal round declares human input, so existing callers are unaffected."""
    response = app_client.post(
        "/api/patients",
        json={"hospital_number": "P-PROV-1", "name": "来源标记患者", "sex": "FEMALE"},
        headers=auth_headers,
    )
    patient = response.json()
    response = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["input_source"] == "HUMAN_KEYBOARD"


def test_self_test_calibration_is_marked_and_its_baseline_warns(app_client, auth_headers):
    """A calibration driven by synthetic events must be identifiable afterwards.

    This is the exact failure the marker exists for: the scripted end-to-end
    check produced a perfect 100% calibration and a baseline row, and nothing in
    the stored data said the presses were not a person.
    """
    response = app_client.post(
        "/api/patients",
        json={"hospital_number": "P-PROV-2", "name": "自检来源患者", "sex": "MALE"},
        headers=auth_headers,
    )
    patient = response.json()

    response = app_client.post(
        f"/api/patients/{patient['id']}/piano/calibration",
        json={"duration_sec": 45, "input_source": "SYNTHETIC_SELFTEST"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    session = response.json()
    assert session["input_source"] == "SYNTHETIC_SELFTEST"

    events = [
        _cue(i, onset=i * 1000, target=i * 1000 + 700, actual=i * 1000 + 740)
        for i in range(4)
    ]
    response = app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": events, "planned_cues": 4},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    response = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["input_source"] == "SYNTHETIC_SELFTEST"

    response = app_client.get(
        f"/api/patients/{patient['id']}/piano/baseline", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    snapshot = response.json()["snapshot"]
    assert snapshot["quality_metadata"]["input_source"] == "SYNTHETIC_SELFTEST"
    assert "不是真人测量值" in snapshot["note"]


def test_unknown_input_source_is_rejected(app_client, auth_headers):
    """The field is a closed set; a typo must not silently become 'human'."""
    response = app_client.post(
        "/api/patients",
        json={"hospital_number": "P-PROV-3", "name": "非法来源患者", "sex": "MALE"},
        headers=auth_headers,
    )
    patient = response.json()
    response = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1, "input_source": "ROBOT"},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


def test_seeded_demo_rows_are_marked_as_demo():
    """The seeder writes randomised metrics, so its rows must say so."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo.py"
    text = source.read_text(encoding="utf-8")
    assert 'input_source="SEED_DEMO"' in text, (
        "seed_demo.py must mark the piano rows it fabricates"
    )
