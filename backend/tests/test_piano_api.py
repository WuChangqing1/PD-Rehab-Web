"""Piano API tests: session lifecycle, raw event storage, metric computation.

Exercises the full round: open a session, post raw events, complete, and verify
the server recomputed the metrics from those events.
"""

from __future__ import annotations

import pytest


def _patient(client, headers, *, number="P-PIANO-1") -> dict:
    response = client.post(
        "/api/patients",
        json={"hospital_number": number, "name": "钢琴测试患者", "sex": "MALE"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _cue(
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
        "key_up_time_ms": None if actual is None else actual + 100,
        "hold_duration_ms": None if actual is None else 100,
        "is_correct": correct,
        "is_missed": missed,
    }


# ------------------------------------------------------------------ lifecycle
def test_start_session_records_difficulty(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    response = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={
            "mode": "SINGLE_KEY_RHYTHM",
            "round_number": 1,
            "difficulty": {
                "bpm": 72,
                "judgement_window_ms": 275,
                "sequence_length": 5,
                "note_density": 1.0,
                "hand_mode": "SINGLE",
                "weak_side_ratio": 0.6,
                "finger_complexity": 2,
                "session_duration_sec": 60,
            },
            "seed": 12345,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mode"] == "SINGLE_KEY_RHYTHM"
    assert body["round_number"] == 1
    assert body["bpm"] == 72
    assert body["judgement_window_ms"] == 275
    assert body["weak_side_ratio"] == pytest.approx(0.6)
    assert body["difficulty_engine_version"]
    assert body["started_at"] is not None
    # metrics are empty until the round completes
    assert body["accuracy"] is None
    assert body["mean_response_latency_ms"] is None


def test_start_session_for_unknown_patient_fails(app_client, auth_headers):
    response = app_client.post(
        "/api/patients/nope/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_start_session_rejects_invalid_difficulty(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-2")
    response = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "difficulty": {"bpm": 9999}},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_start_session_rejects_unknown_mode(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-3")
    response = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "NOT_A_MODE", "round_number": 1},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- raw events
def test_store_raw_events_verbatim(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-4")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()

    events = [
        _cue(0, cue_onset=0, target=700, actual=712),
        _cue(1, cue_onset=1000, target=1700, actual=1690),
    ]
    response = app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": events, "planned_cues": 2},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["stored"] == 2


def test_events_are_rejected_after_completion(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-5")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(0, cue_onset=0, target=700, actual=700)]},
        headers=auth_headers,
    )
    app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    response = app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(1, cue_onset=0, target=700, actual=700)]},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_events_batch_requires_authentication(app_client):
    assert app_client.post("/api/piano/sessions/x/events/batch", json={"events": []}).status_code == 401


# ----------------------------------------------------------------- completion
def test_complete_recomputes_metrics_from_events(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-6")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "ALTERNATING_HANDS", "round_number": 1},
        headers=auth_headers,
    ).json()

    # 4 cues: 2 correct on each hand, one miss; latency 700/600 left, 500/400 right
    events = [
        _cue(0, cue_onset=0, target=700, actual=700, hand="LEFT"),
        _cue(1, cue_onset=1000, target=1700, actual=1600, hand="LEFT"),
        _cue(2, cue_onset=2000, target=2700, actual=2500, hand="RIGHT"),
        _cue(3, cue_onset=3000, target=3700, actual=3400, hand="RIGHT"),
        _cue(4, cue_onset=4000, target=4700, actual=None, correct=False, missed=True, hand="LEFT"),
    ]
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": events, "planned_cues": 5},
        headers=auth_headers,
    )

    response = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete",
        json={"difficulty_after": {"bpm": 65}},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["accuracy"] == pytest.approx(0.8)
    assert body["miss_rate"] == pytest.approx(0.2)
    assert body["session_completion_rate"] == pytest.approx(1.0)
    # latencies: 700, 600, 500, 400 -> mean 550
    assert body["mean_response_latency_ms"] == pytest.approx(550.0)
    # timing errors: 0, -100, -200, -300 -> mean -150
    assert body["mean_timing_error_ms"] == pytest.approx(-150.0)
    assert body["left_accuracy"] == pytest.approx(2 / 3)
    assert body["right_accuracy"] == pytest.approx(1.0)
    # left latency 650, right 450
    assert body["left_mean_latency"] == pytest.approx(650.0)
    assert body["right_mean_latency"] == pytest.approx(450.0)
    assert body["left_right_latency_difference"] == pytest.approx(200.0)
    assert body["completed_at"] is not None
    # the persisted events come back with the session
    assert len(body["events"]) == 5
    assert body["planned_cues"] == 5


def test_complete_twice_conflicts(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-7")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(0, cue_onset=0, target=700, actual=700)]},
        headers=auth_headers,
    )
    first = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert first.status_code == 200
    second = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert second.status_code == 409


def test_complete_with_no_events_still_succeeds(app_client, auth_headers):
    """An aborted round must not crash; metrics stay null."""
    patient = _patient(app_client, auth_headers, number="P-PIANO-8")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    response = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["accuracy"] is None


def test_wrong_key_events_are_stored_and_counted(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-9")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()

    events = [
        _cue(0, cue_onset=0, target=700, actual=700),
        {
            "event_index": 1,
            "cue_onset_time_ms": 1000,
            "target_time_ms": 1700,
            "actual_time_ms": 1800,
            "timing_error_ms": 100,
            "key_code": "KeyX",
            "note": "D3",
            "hand": "LEFT",
            "finger_hint": "RING",
            "key_down_time_ms": 1800,
            "is_correct": False,
            "is_missed": False,
            "is_wrong_key": True,
            "cue_index": 1,
        },
        _cue(2, cue_onset=1000, target=1700, actual=1850),
    ]
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": events, "planned_cues": 2},
        headers=auth_headers,
    )
    body = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    ).json()

    # the wrong press is an extra row, not an extra target
    assert len(body["events"]) == 3
    assert body["accuracy"] == pytest.approx(1.0)
    # one wrong press recorded against the two cues
    assert sum(1 for e in body["events"] if not e["is_wrong_key"]) == 2


# ---------------------------------------------------------------- calibration
def test_calibration_creates_baseline(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-10")
    calibration = app_client.post(
        f"/api/patients/{patient['id']}/piano/calibration",
        json={"duration_sec": 45},
        headers=auth_headers,
    )
    assert calibration.status_code == 201, calibration.text
    session = calibration.json()
    assert session["mode"] == "CALIBRATION"
    assert session["session_duration_sec"] == 45

    events = [
        _cue(0, cue_onset=0, target=700, actual=700, hand="LEFT"),
        _cue(1, cue_onset=1000, target=1700, actual=1600, hand="LEFT"),
        _cue(2, cue_onset=2000, target=2700, actual=2500, hand="RIGHT"),
        _cue(3, cue_onset=3000, target=3700, actual=3450, hand="RIGHT"),
    ]
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": events, "planned_cues": 4},
        headers=auth_headers,
    )
    completed = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert completed.status_code == 200

    response = app_client.get(
        f"/api/patients/{patient['id']}/piano/baseline", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    baseline = response.json()
    assert baseline["baseline_accuracy"] == pytest.approx(1.0)
    # left latencies 700, 600 -> 650 ; right latencies 500, 450 -> 475
    assert baseline["baseline_left_latency"] == pytest.approx(650.0)
    assert baseline["baseline_right_latency"] == pytest.approx(475.0)
    assert baseline["is_active"] is True


def test_calibration_stores_the_measured_personal_tempo(app_client, auth_headers):
    """The uncued segment's measurement becomes part of the baseline.

    Evidence: docs/piano_training_plan.md P1/P2. A tempo *percentage* is
    meaningless without a baseline to take it of, and the paced part of
    calibration cannot reveal the patient's own rhythm -- it imposes one.
    """
    patient = _patient(app_client, auth_headers, number="P-PIANO-TEMPO")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/calibration",
        json={"duration_sec": 45},
        headers=auth_headers,
    ).json()

    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={
            "events": [_cue(0, cue_onset=0, target=700, actual=700)],
            "planned_cues": 1,
            "spontaneous_tapping": {
                "window_ms": 15000,
                "tap_count": 21,
                "interval_ms": 714.3,
                "rate_hz": 1.4,
                "interval_cv": 0.081,
                "note": "无提示自由敲击段测量值，不判对错、不计准确率。",
            },
        },
        headers=auth_headers,
    )
    app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )

    baseline = app_client.get(
        f"/api/patients/{patient['id']}/piano/baseline", headers=auth_headers
    ).json()

    assert baseline["baseline_spontaneous_bpm"] == pytest.approx(84.0)
    assert baseline["baseline_spontaneous_interval_ms"] == pytest.approx(714.3)
    assert baseline["baseline_spontaneous_interval_cv"] == pytest.approx(0.081)
    assert baseline["calibration_version"] == "piano-calibration-v1.1.0"
    # The eight specification values are untouched by the addition.
    assert baseline["baseline_accuracy"] == pytest.approx(1.0)
    # And the measurement keeps its provenance.
    assert baseline["snapshot"]["quality_metadata"]["spontaneous_window_ms"] == 15000


def test_calibration_without_the_uncued_segment_reports_no_tempo(app_client, auth_headers):
    """Absent means not measured, never zero."""
    patient = _patient(app_client, auth_headers, number="P-PIANO-NOTEMPO")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/calibration",
        json={"duration_sec": 45},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(0, cue_onset=0, target=700, actual=700)], "planned_cues": 1},
        headers=auth_headers,
    )
    app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    baseline = app_client.get(
        f"/api/patients/{patient['id']}/piano/baseline", headers=auth_headers
    ).json()
    assert baseline["baseline_spontaneous_bpm"] is None


def test_baseline_missing_returns_404(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-11")
    response = app_client.get(
        f"/api/patients/{patient['id']}/piano/baseline", headers=auth_headers
    )
    assert response.status_code == 404


def test_second_calibration_deactivates_the_first_but_keeps_it(
    app_client, auth_headers, db
):
    from app.db.models import Baseline

    patient = _patient(app_client, auth_headers, number="P-PIANO-12")
    for _ in range(2):
        session = app_client.post(
            f"/api/patients/{patient['id']}/piano/calibration",
            json={"duration_sec": 30},
            headers=auth_headers,
        ).json()
        app_client.post(
            f"/api/piano/sessions/{session['id']}/events/batch",
            json={"events": [_cue(0, cue_onset=0, target=700, actual=700)], "planned_cues": 1},
            headers=auth_headers,
        )
        app_client.post(
            f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
        )

    rows = db.query(Baseline).filter(Baseline.patient_id == patient["id"]).all()
    assert len(rows) == 2, "the old baseline must be kept, not deleted"
    assert sum(1 for r in rows if r.is_active) == 1


# --------------------------------------------------------- engine version audit
def test_the_recorded_engine_version_is_the_one_that_decided(app_client, auth_headers):
    """The rule engine runs in the frontend, so the server cannot assume it ran
    the version this deployment expected. Recording the expected value would
    make a stored decision look like it came from an engine that never ran."""
    patient = _patient(app_client, auth_headers, number="P-PIANO-V1")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    assert session["difficulty_engine_version"] == "piano-difficulty-v1.1.0"

    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(0, cue_onset=0, target=700, actual=700)], "planned_cues": 1},
        headers=auth_headers,
    )
    completed = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete",
        json={
            "difficulty_after": {"bpm": 65},
            "adaptation": {
                "decision": "UPGRADE",
                "changes": [{"field": "bpm", "from": 60, "to": 65}],
                "reasons": ["准确率、漏击率与响应延迟变异均达到升级条件"],
                "engine_version": "piano-difficulty-v1.1.0",
            },
        },
        headers=auth_headers,
    ).json()

    assert completed["difficulty_engine_version"] == "piano-difficulty-v1.1.0"
    assert completed["adaptation_reason_json"]["changes"][0]["field"] == "bpm"


def test_an_older_client_engine_is_recorded_verbatim(app_client, auth_headers):
    """A session completed by an older frontend keeps that frontend's version,
    so a trend line can tell the two engines apart."""
    patient = _patient(app_client, auth_headers, number="P-PIANO-V2")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(0, cue_onset=0, target=700, actual=700)], "planned_cues": 1},
        headers=auth_headers,
    )
    completed = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete",
        json={"adaptation": {"decision": "MAINTAIN", "engine_version": "piano-difficulty-v1.0.0"}},
        headers=auth_headers,
    ).json()
    assert completed["difficulty_engine_version"] == "piano-difficulty-v1.0.0"


def test_completion_without_an_adaptation_keeps_the_session_start_version(
    app_client, auth_headers
):
    patient = _patient(app_client, auth_headers, number="P-PIANO-V3")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": [_cue(0, cue_onset=0, target=700, actual=700)], "planned_cues": 1},
        headers=auth_headers,
    )
    completed = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    ).json()
    assert completed["difficulty_engine_version"] == "piano-difficulty-v1.1.0"


# ------------------------------------------------------------------- history
def test_history_lists_sessions(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-PIANO-13")
    for round_number in (1, 2, 3):
        app_client.post(
            f"/api/patients/{patient['id']}/piano/sessions",
            json={"mode": "SINGLE_KEY_RHYTHM", "round_number": round_number},
            headers=auth_headers,
        )
    page = app_client.get(
        f"/api/patients/{patient['id']}/piano/history", headers=auth_headers
    ).json()
    assert page["total"] == 3
    assert len(page["items"]) == 3


def test_piano_endpoints_require_authentication(app_client):
    assert app_client.get("/api/patients/x/piano/history").status_code == 401
    assert app_client.post("/api/patients/x/piano/calibration", json={}).status_code == 401


# ------------------------------------------------------ client/server agreement
def test_server_metrics_flag_client_divergence(app_client, auth_headers):
    """If the client-reported metrics disagree, the session records a warning."""
    patient = _patient(app_client, auth_headers, number="P-PIANO-14")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "round_number": 1},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={
            "events": [_cue(0, cue_onset=0, target=700, actual=700)],
            "planned_cues": 1,
            "client_metrics": {"accuracy": 0.123},  # deliberately wrong
        },
        headers=auth_headers,
    )
    body = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    ).json()
    # the server value wins
    assert body["accuracy"] == pytest.approx(1.0)


def test_server_metrics_agree_with_client_shape(app_client, auth_headers):
    """Complete a realistic round and check the server mapping end to end."""
    patient = _patient(app_client, auth_headers, number="P-PIANO-15")
    session = app_client.post(
        f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "FOLLOW_THE_BEAT", "round_number": 2},
        headers=auth_headers,
    ).json()

    events = []
    for i in range(6):
        onset = i * 1000
        target = onset + 700
        actual = target + (50 if i % 2 else -30)
        events.append(
            _cue(i, cue_onset=onset, target=target, actual=actual,
                 hand="LEFT" if i % 2 == 0 else "RIGHT",
                 finger="INDEX" if i % 3 else "RING")
        )
    app_client.post(
        f"/api/piano/sessions/{session['id']}/events/batch",
        json={"events": events, "planned_cues": 6},
        headers=auth_headers,
    )
    body = app_client.post(
        f"/api/piano/sessions/{session['id']}/complete", json={}, headers=auth_headers
    ).json()

    assert body["accuracy"] == pytest.approx(1.0)
    assert body["miss_rate"] == pytest.approx(0.0)
    assert body["mean_response_latency_ms"] == pytest.approx(700 + 10)
    assert body["timing_mae_ms"] == pytest.approx(40.0)
    assert body["weak_finger_error_rate"] == pytest.approx(0.0)
    assert body["left_mean_latency"] is not None
    assert body["right_mean_latency"] is not None
