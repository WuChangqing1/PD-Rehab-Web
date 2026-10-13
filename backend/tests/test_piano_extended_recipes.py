"""New recipe lifecycle against the per-test SQLite DB, never patient data."""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.db.models import PianoSession
from app.schemas.piano import DifficultyConfigSchema, PianoCalibrationRequest, PianoEventIn, PianoEventsBatch, PianoSessionCreate
from app.utils.piano_metrics import compute_metrics
from tests.test_piano_api import _cue, _patient


def event(index, recipe, *, actual=None, correct=True, missed=False, **extra):
    row = _cue(index, cue_onset=index * 1000, target=index * 1000 + 500,
               actual=actual, correct=correct, missed=missed)
    return {**row, "cue_index": index, "recipe_id": recipe, **extra}


CASES = [
    ("TEMPO_RAMP", "SINGLE_KEY_RHYTHM", [
        event(0, "TEMPO_RAMP", actual=520, tempo_segment=0),
        event(1, "TEMPO_RAMP", correct=False, missed=True, tempo_segment=0),
        event(2, "TEMPO_RAMP", actual=2470, tempo_segment=3),
    ], {"tempo_segment_0_accuracy": 0.5, "tempo_segment_0_mae_ms": 20,
        "tempo_segment_3_accuracy": 1.0, "tempo_segment_3_mae_ms": 30}),
    ("HOLD_RELEASE", "SINGLE_KEY_RHYTHM", [
        event(0, "HOLD_RELEASE", actual=500, target_hold_ms=250,
              key_up_time_ms=800, hold_duration_ms=9999),
        event(1, "HOLD_RELEASE", actual=1500, target_hold_ms=750,
              key_up_time_ms=None, hold_duration_ms=750),
        event(2, "HOLD_RELEASE", correct=False, missed=True, target_hold_ms=250),
    ], {"hold_duration_mae_ms": 50, "hold_release_completion_rate": 1 / 3}),
    ("BIMANUAL_OFFSET", "SINGLE_KEY_RHYTHM", [
        event(0, "BIMANUAL_OFFSET", actual=500, pair_id=0, pair_role="PRIMARY",
              target_offset_ms=250, inter_hand_onset_diff_ms=9999),
        event(1, "BIMANUAL_OFFSET", actual=800, pair_id=0, pair_role="SECONDARY",
              hand="RIGHT", target_offset_ms=250, inter_hand_onset_diff_ms=9999),
        event(2, "BIMANUAL_OFFSET", correct=False, missed=True, pair_id=1,
              pair_role="PRIMARY", target_offset_ms=250),
        event(3, "BIMANUAL_OFFSET", actual=3800, pair_id=1,
              pair_role="SECONDARY", hand="RIGHT", target_offset_ms=250),
    ], {"inter_hand_phase_mae_ms": 50, "offset_left_miss_rate": 0.5,
        "offset_right_miss_rate": 0.0}),
    ("REVERSE_SEQUENCE", "MEMORY_RHYTHM", [
        event(0, "REVERSE_SEQUENCE", correct=False, missed=True, is_prompt=True,
              memory_group=0, sequence_position=1, sequence_length=2),
        event(1, "REVERSE_SEQUENCE", actual=1500, memory_group=0,
              sequence_position=1, sequence_length=2),
        event(2, "REVERSE_SEQUENCE", actual=2500, memory_group=0,
              sequence_position=2, sequence_length=2),
        event(3, "REVERSE_SEQUENCE", actual=3500, memory_group=1,
              sequence_position=1, sequence_length=2),
    ], {"reverse_position_accuracy": 1.0, "reverse_completion_rate": 0.5}),
    ("GO_NO_GO", "SINGLE_KEY_RHYTHM", [
        event(0, "GO_NO_GO", actual=500, cue_type="GO", response_latency_ms=9999),
        event(1, "GO_NO_GO", cue_type="NO_GO"),
        event(2, "GO_NO_GO", actual=2500, correct=False, cue_type="NO_GO"),
        event(3, "GO_NO_GO", correct=False, missed=True, cue_type="GO"),
        event(4, "GO_NO_GO", actual=4500, correct=False, cue_type="NO_GO",
              is_wrong_key=True, cue_index=2),
    ], {"go_commission_count": 1, "go_omission_count": 1,
        "go_response_latency_ms": 500}),
]


@pytest.mark.parametrize("recipe,mode,events,expected", CASES)
def test_new_recipe_raw_events_survive_retry_complete_and_read(
    app_client, auth_headers, recipe, mode, events, expected
):
    patient = _patient(app_client, auth_headers)
    response = app_client.post(f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": mode, "recipe_id": recipe, "input_source": "SYNTHETIC_SELFTEST"},
        headers=auth_headers)
    assert response.status_code == 201, response.text
    session = response.json()
    assert session["input_source"] == "SYNTHETIC_SELFTEST"
    assert session["difficulty_before_json"]["recipe_algorithm_version"] == "piano-recipe-v2.0.0"
    path = f"/api/piano/sessions/{session['id']}"
    # Two separate batches expose metadata overwrites; repeated first batch
    # exposes duplicate event rows and changed metrics on a network retry.
    first = {"events": events[:1], "planned_cues": len(events)}
    assert app_client.post(path + "/events/batch", json=first, headers=auth_headers).json()["stored"] == 1
    retry = app_client.post(path + "/events/batch", json=first, headers=auth_headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["stored"] == 0
    saved = app_client.post(path + "/events/batch", json={"events": events[1:]}, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    completed = app_client.post(path + "/complete", json={"interrupted": True}, headers=auth_headers)
    assert completed.status_code == 200, completed.text
    detail = app_client.get(path, headers=auth_headers).json()
    assert len(detail["events"]) == len(events)
    assert detail["planned_cues"] == len(events)
    audit = detail["difficulty_before_json"]
    assert audit["completion_status"] == "INTERRUPTED"
    for raw, stored in zip(events, detail["events"]):
        for key, value in raw.items():
            assert stored[key] == value, key
    metrics = audit["server_metrics"]
    for key, value in expected.items():
        assert metrics[key] == pytest.approx(value), key
    if recipe == "TEMPO_RAMP":
        assert metrics["tempo_segments"] == [
            {"segment": 0, "accuracy": 0.5, "timing_mae_ms": 20.0, "miss_rate": 0.5, "cue_count": 2},
            {"segment": 3, "accuracy": 1.0, "timing_mae_ms": 30.0, "miss_rate": 0.0, "cue_count": 1},
        ]
    if recipe == "GO_NO_GO":
        assert metrics["total_cues"] == 4
        assert metrics["missed_count"] == 1
    if recipe == "REVERSE_SEQUENCE":
        assert metrics["total_cues"] == 3


@pytest.mark.parametrize("field,value", [
    ("tempo_segment", -1), ("tempo_segment", 4), ("tempo_segment", 1.5),
    ("target_hold_ms", 0), ("pair_id", -1), ("target_offset_ms", -1),
    ("cue_type", "WAIT"), ("recipe_id", "UNSUPPORTED"),
])
def test_invalid_extended_event_fields_rejected(field, value):
    with pytest.raises(ValidationError):
        PianoEventIn.model_validate({"event_index": 0, "is_correct": True,
                                    "is_missed": False, field: value})


def test_no_go_does_not_contribute_timing_latency_or_misses():
    rows = [event(0, "GO_NO_GO", actual=520, cue_type="GO"),
            event(1, "GO_NO_GO", cue_type="NO_GO", response_latency_ms=99,
                  timing_error_ms=99)]
    metrics = compute_metrics(rows).to_dict()
    assert metrics["mean_response_latency_ms"] == 520
    assert metrics["mean_absolute_timing_error_ms"] == 20
    assert metrics["left_mean_latency"] == 520
    assert metrics["missed_count"] == 0


@pytest.mark.parametrize("positions,expected", [([1, 2, 3], 1.0), ([1, 3], 0.0)])
def test_reverse_completion_uses_one_based_sequence_positions(positions, expected):
    rows = [event(i, "REVERSE_SEQUENCE", actual=i * 1000 + 500,
                  memory_group=0, sequence_position=position, sequence_length=3)
            for i, position in enumerate(positions)]
    metrics = compute_metrics(rows)
    assert metrics.reverse_completion_rate == expected


def test_old_recipe_version_and_normal_completion_remain_readable(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    created = app_client.post(f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "recipe_id": "SFT_CUE_SYNC"}, headers=auth_headers).json()
    path = f"/api/piano/sessions/{created['id']}"
    response = app_client.post(path + "/complete", json={}, headers=auth_headers)
    assert response.status_code == 200
    audit = response.json()["difficulty_before_json"]
    assert audit["recipe_algorithm_version"] == "piano-recipe-v1.0.0"
    assert audit["completion_status"] == "COMPLETED"


def test_api_rejects_invalid_recipe_mode_and_event_metadata(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    path = f"/api/patients/{patient['id']}/piano/sessions"
    for payload in [{"mode": "SINGLE_KEY_RHYTHM", "recipe_id": "UNKNOWN"},
                    {"mode": "SINGLE_KEY_RHYTHM", "recipe_id": "REVERSE_SEQUENCE"}]:
        assert app_client.post(path, json=payload, headers=auth_headers).status_code == 422
    created = app_client.post(path, json={"mode": "SINGLE_KEY_RHYTHM"}, headers=auth_headers).json()
    response = app_client.post(f"/api/piano/sessions/{created['id']}/events/batch",
        json={"events": [event(0, "SFT_CUE_SYNC", tempo_segment=4)]}, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.parametrize("calibration", [False, True])
def test_deferred_session_keeps_actual_start_time(app_client, auth_headers, calibration):
    patient = _patient(app_client, auth_headers)
    started = datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = {"started_at": started.isoformat()}
    if not calibration:
        payload["mode"] = "SINGLE_KEY_RHYTHM"
    endpoint = "calibration" if calibration else "sessions"
    response = app_client.post(f"/api/patients/{patient['id']}/piano/{endpoint}",
                               json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    # SQLite stores the UTC instant without its offset.
    stored = datetime.fromisoformat(response.json()["started_at"]).replace(tzinfo=timezone.utc)
    assert stored == started


@pytest.mark.parametrize("schema", [PianoSessionCreate, PianoCalibrationRequest])
@pytest.mark.parametrize("started", ["2026-01-01T00:00:00", "2099-01-01T00:00:00Z"])
def test_started_at_rejects_ambiguous_or_future_time(schema, started):
    with pytest.raises(ValidationError):
        schema.model_validate({"mode": "SINGLE_KEY_RHYTHM", "started_at": started})


def test_conflicting_retry_cannot_replace_raw_evidence(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    created = app_client.post(f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM"}, headers=auth_headers).json()
    path = f"/api/piano/sessions/{created['id']}"
    row = event(0, "SFT_CUE_SYNC", actual=500)
    app_client.post(path + "/events/batch", json={"events": [row, row]}, headers=auth_headers)
    response = app_client.post(path + "/events/batch",
        json={"events": [{**row, "actual_time_ms": 700}]}, headers=auth_headers)
    assert response.status_code == 409
    detail = app_client.get(path, headers=auth_headers).json()
    assert len(detail["events"]) == 1
    assert detail["events"][0]["actual_time_ms"] == 500


def test_interrupted_calibration_keeps_previous_active_baseline(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    create_path = f"/api/patients/{patient['id']}/piano/calibration"
    baseline_path = f"/api/patients/{patient['id']}/piano/baseline"
    # HUMAN_KEYBOARD is intentional here to exercise the active-baseline gate;
    # all measurements still live solely in this test's temporary database.
    first = app_client.post(create_path, json={}, headers=auth_headers).json()
    app_client.post(f"/api/piano/sessions/{first['id']}/events/batch",
        json={"events": [event(0, None, actual=500)]}, headers=auth_headers)
    app_client.post(f"/api/piano/sessions/{first['id']}/complete", json={}, headers=auth_headers)
    original = app_client.get(baseline_path, headers=auth_headers).json()
    second = app_client.post(create_path, json={}, headers=auth_headers).json()
    app_client.post(f"/api/piano/sessions/{second['id']}/events/batch",
        json={"events": [event(0, None, actual=550)]}, headers=auth_headers)
    completed = app_client.post(f"/api/piano/sessions/{second['id']}/complete",
        json={"interrupted": True}, headers=auth_headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["completed_at"] is not None
    assert completed.json()["difficulty_before_json"]["completion_status"] == "INTERRUPTED"
    current = app_client.get(baseline_path, headers=auth_headers).json()
    assert current["id"] == original["id"]
    assert current["baseline_response_latency"] == original["baseline_response_latency"]


def test_raw_presses_store_prompt_and_extra_input_without_changing_cue_metrics(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    created = app_client.post(f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM", "recipe_id": "HOLD_RELEASE"}, headers=auth_headers).json()
    path = f"/api/piano/sessions/{created['id']}"
    presses = [{"key_code": "KeyZ", "midi": 48, "key_down_time_ms": 100, "key_up_time_ms": 160},
               {"key_code": "KeyZ", "midi": 48, "key_down_time_ms": 200, "key_up_time_ms": None}]
    payload = {"events": [event(0, "HOLD_RELEASE", actual=500, target_hold_ms=100)],
               "raw_presses": presses}
    response = app_client.post(path + "/events/batch", json=payload, headers=auth_headers)
    assert response.status_code == 200, response.text
    app_client.post(path + "/events/batch", json=payload, headers=auth_headers)
    completed = app_client.post(path + "/complete", json={}, headers=auth_headers).json()
    detail = app_client.get(path, headers=auth_headers).json()
    assert detail["difficulty_before_json"]["raw_presses"] == presses
    assert completed["difficulty_before_json"]["server_metrics"]["total_cues"] == 1


@pytest.mark.parametrize("override", [{"midi": 128}, {"key_down_time_ms": -1},
                                      {"key_up_time_ms": 90}, {"key_code": "x" * 33}])
def test_invalid_raw_press_timestamps_or_mapping_rejected(override):
    row = {"key_code": "KeyZ", "midi": 48, "key_down_time_ms": 100, "key_up_time_ms": 150, **override}
    with pytest.raises(ValidationError):
        PianoEventsBatch.model_validate({"events": [event(0, None)], "raw_presses": [row]})


@pytest.mark.parametrize("calibration", [False, True])
def test_client_request_id_retries_reuse_session_without_crossing_patient(
    app_client, auth_headers, db, calibration
):
    first_patient = _patient(app_client, auth_headers, number="RETRY-1")
    second_patient = _patient(app_client, auth_headers, number="RETRY-2")
    endpoint = "calibration" if calibration else "sessions"
    payload = {"client_request_id": "retry-round-1"}
    if not calibration:
        payload.update(mode="SINGLE_KEY_RHYTHM", recipe_id="HOLD_RELEASE")
    path = f"/api/patients/{first_patient['id']}/piano/{endpoint}"
    first = app_client.post(path, json=payload, headers=auth_headers)
    repeated = app_client.post(path, json=payload, headers=auth_headers)
    assert first.status_code == repeated.status_code == 201
    assert repeated.json()["id"] == first.json()["id"]
    assert first.json()["difficulty_before_json"]["client_request_id"] == "retry-round-1"
    other = app_client.post(f"/api/patients/{second_patient['id']}/piano/{endpoint}",
                            json=payload, headers=auth_headers)
    assert other.status_code == 201
    assert other.json()["id"] != first.json()["id"]
    assert db.scalar(select(func.count()).select_from(PianoSession)) == 2


def test_client_request_id_cannot_change_recipe_or_input_source(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    path = f"/api/patients/{patient['id']}/piano/sessions"
    payload = {"mode": "SINGLE_KEY_RHYTHM", "recipe_id": "HOLD_RELEASE",
               "client_request_id": "retry-round-1", "input_source": "SYNTHETIC_SELFTEST"}
    assert app_client.post(path, json=payload, headers=auth_headers).status_code == 201
    for override in [{"recipe_id": "TEMPO_RAMP"}, {"input_source": "HUMAN_KEYBOARD"}]:
        response = app_client.post(path, json={**payload, **override}, headers=auth_headers)
        assert response.status_code == 409


@pytest.mark.parametrize("override", [
    {"difficulty": {"bpm": 90}}, {"seed": 44}, {"round_number": 2}, {"weak_hand": "LEFT"},
])
def test_client_request_id_cannot_change_collected_round_configuration(app_client, auth_headers, override):
    patient = _patient(app_client, auth_headers)
    path = f"/api/patients/{patient['id']}/piano/sessions"
    payload = {"mode": "SINGLE_KEY_RHYTHM", "client_request_id": "stable-round",
               "difficulty": {"bpm": 72}, "seed": 43, "round_number": 1, "weak_hand": "RIGHT"}
    first = app_client.post(path, json=payload, headers=auth_headers)
    response = app_client.post(path, json={**payload, **override}, headers=auth_headers)
    assert response.status_code == 409
    detail = app_client.get(f"/api/piano/sessions/{first.json()['id']}", headers=auth_headers).json()
    assert detail["bpm"] == 72
    assert detail["round_number"] == 1


@pytest.mark.parametrize("ceiling", [39, 161, float("inf"), float("nan")])
def test_tempo_ceiling_rejects_out_of_range_or_nonfinite_value(ceiling):
    with pytest.raises(ValidationError):
        DifficultyConfigSchema.model_validate({"tempo_ceiling_bpm": ceiling})


@pytest.mark.parametrize("ceiling", [40, 90.5, 160, None])
def test_tempo_ceiling_snapshot_and_retry_keep_same_configuration(app_client, auth_headers, ceiling):
    patient = _patient(app_client, auth_headers)
    path = f"/api/patients/{patient['id']}/piano/sessions"
    payload = {"mode": "SINGLE_KEY_RHYTHM", "recipe_id": "TEMPO_RAMP",
               "client_request_id": "tempo-cap-round", "difficulty": {"tempo_ceiling_bpm": ceiling}}
    first = app_client.post(path, json=payload, headers=auth_headers)
    assert first.status_code == 201, first.text
    assert first.json()["difficulty_before_json"]["tempo_ceiling_bpm"] == ceiling
    retry = app_client.post(path, json=payload, headers=auth_headers)
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    changed = app_client.post(path, json={**payload, "difficulty": {"tempo_ceiling_bpm": 100}},
                              headers=auth_headers)
    assert changed.status_code == 409


@pytest.mark.parametrize("request_id", ["", "x" * 65])
def test_client_request_id_bounds(request_id):
    with pytest.raises(ValidationError):
        PianoSessionCreate.model_validate({"mode": "SINGLE_KEY_RHYTHM", "client_request_id": request_id})
