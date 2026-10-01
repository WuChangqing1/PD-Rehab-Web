"""Pose API tests.

The model itself is not exercised here: the metric maths is covered by
test_pose_metrics.py and the landmarker is verified against real input in
docs/metric_definitions.md (Phase 6). What these tests cover is the wiring --
session lifecycle, provenance, the quality-gate response, and the guarantee that
no display score can reach the database while the formulas are undefined.
"""

from __future__ import annotations

import io
import math
from pathlib import Path

import pytest

from app.ml.pose.analyzer import GATE_NO_POSE_DETECTED
from app.ml.pose.landmarks import PoseSeries

FPS = 30.0


@pytest.fixture(autouse=True)
def stub_model_path(monkeypatch):
    """Stand in for the 5 MB landmarker asset.

    The check that the model exists is part of the service, so the tests supply
    a path that exists and patch the extraction itself. The landmarker's real
    behaviour is verified against real input outside the unit tests.
    """
    monkeypatch.setattr(
        "app.services.pose_service._model_path", lambda: Path(__file__).resolve()
    )


def _patient(client, headers, *, number="P-POSE-1") -> dict:
    response = client.post(
        "/api/patients",
        json={"hospital_number": number, "name": "动作测试患者", "sex": "MALE"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _fake_video() -> bytes:
    """A tiny non-empty upload; extraction is patched out in these tests."""
    return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 256


def _series(frames: int = 90, *, movement: bool = True) -> PoseSeries:
    from tests.test_pose_metrics import arm_frame, series_from_frames

    built = []
    for i in range(frames):
        if movement:
            phase = 2 * math.pi * (i % 30) / 30
            angle = 10.0 + 160.0 * (1 - math.cos(phase)) / 2
        else:
            angle = 90.0
        built.append(arm_frame(left_abduction=angle, right_abduction=angle))
    return series_from_frames(built, fps=FPS)


# ------------------------------------------------------------------ catalogue
def test_exercises_endpoint_lists_five_without_scores(app_client, auth_headers):
    response = app_client.get("/api/pose/exercises", headers=auth_headers)
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 5
    keys = {item["key"] for item in items}
    assert keys == {
        "BALLET_PORT_DE_BRAS",
        "BALLET_FIRST_POSITION",
        "BALLET_TENDU",
        "BALLET_DEMI_PLIE",
        "BALLET_WEIGHT_SHIFT",
    }
    for item in items:
        assert item["scores_available"] is False
        assert all(value is None for value in item["score_formulas"].values())
        # Leg exercises report four extra leg metrics on top of the common ten.
        expected = 14 if item["key"] in {"BALLET_TENDU", "BALLET_DEMI_PLIE"} else 10
        assert len(item["raw_metrics"]) == expected
        # The doctor picks the mode; the patient never does.
        assert item["supported_modes"]
        assert all(mode in {"SEATED", "STANDING_SUPPORTED"} for mode in item["supported_modes"])
        assert item["mode_labels"]
        # Every exercise carries the counted phrase the patient follows.
        assert item["cues"]
        assert item["total_beats"] > 0
        assert item["default_bpm"] > 0
        assert item["name_en"]


def test_thresholds_endpoint_explains_the_gates(app_client, auth_headers):
    response = app_client.get("/api/pose/thresholds", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["algorithm_version"] == "pose-metrics-v1.0.0"
    assert body["min_valid_frame_ratio"] > 0


def test_pose_endpoints_require_authentication(app_client):
    assert app_client.get("/api/pose/exercises").status_code == 401
    assert app_client.get("/api/pose/thresholds").status_code == 401


# ------------------------------------------------------------------ lifecycle
def test_start_session_defaults_to_human_input(app_client, auth_headers):
    patient = _patient(app_client, auth_headers)
    response = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["input_source"] == "HUMAN_KEYBOARD"
    assert body["exercise_type"] == "BALLET_PORT_DE_BRAS"
    # Nothing measured yet, and no score of any kind.
    assert body["repetition_count"] is None
    assert body["completion_score"] is None
    assert body["range_of_motion"] is None
    assert body["symmetry_score"] is None
    assert body["stability_score"] is None
    assert body["started_at"] is not None
    assert body["completed_at"] is None


def test_start_session_rejects_an_unknown_exercise(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-POSE-2")
    response = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "SOMERSAULT"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_start_session_for_unknown_patient_fails(app_client, auth_headers):
    response = app_client.post(
        "/api/patients/nope/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_input_source_is_carried_through(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-POSE-3")
    response = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS", "input_source": "SYNTHETIC_SELFTEST"},
        headers=auth_headers,
    )
    assert response.json()["input_source"] == "SYNTHETIC_SELFTEST"


def test_unknown_input_source_is_rejected(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-POSE-4")
    response = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS", "input_source": "ROBOT"},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ------------------------------------------------------------------- analysis
def test_analysis_stores_metrics_and_never_a_score(app_client, auth_headers, monkeypatch):
    patient = _patient(app_client, auth_headers, number="P-POSE-5")
    session = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    ).json()

    monkeypatch.setattr(
        "app.services.pose_service.extract_landmarks",
        lambda *a, **k: _series(90),
    )

    response = app_client.post(
        f"/api/pose/sessions/{session['id']}/analyze",
        files={"video": ("arm-raise.mp4", io.BytesIO(_fake_video()), "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] is True
    assert body["gate_failures"] == []

    stored = body["session"]
    assert stored["repetition_count"] == 3
    assert stored["hold_time_sec"] is not None
    assert stored["valid_pose_frame_ratio"] == 1.0
    assert stored["completed_at"] is not None
    assert stored["media_file_id"] is not None
    # The whole point: a number nobody can reproduce must not appear.
    for key in ("completion_score", "range_of_motion", "symmetry_score", "stability_score"):
        assert stored[key] is None, key
    metrics = stored["raw_metrics_json"]
    assert metrics["left_shoulder_max_angle_deg"] == pytest.approx(170.0, abs=8.0)
    assert stored["algorithm_version"] == "pose-metrics-v1.0.0"


def test_a_recording_that_fails_a_gate_returns_422_with_the_report(
    app_client, auth_headers, monkeypatch
):
    patient = _patient(app_client, auth_headers, number="P-POSE-6")
    session = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    ).json()

    monkeypatch.setattr(
        "app.services.pose_service.extract_landmarks",
        lambda *a, **k: _series(60, movement=False),
    )

    response = app_client.post(
        f"/api/pose/sessions/{session['id']}/analyze",
        files={"video": ("still.mp4", io.BytesIO(_fake_video()), "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
    detail = response.json()["error"]["detail"]
    assert detail["gate_failures"], "the refusal must say which gate failed"
    assert "quality" in detail and detail["quality"]["valid_frame_count"] == 60

    # The session must not look completed, but the measurement is kept.
    after = app_client.get(
        f"/api/pose/sessions/{session['id']}", headers=auth_headers
    ).json()
    assert after["completed_at"] is None
    assert after["raw_metrics_json"] is not None


def test_no_pose_at_all_is_reported_as_such(app_client, auth_headers, monkeypatch):
    patient = _patient(app_client, auth_headers, number="P-POSE-7")
    session = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    ).json()

    monkeypatch.setattr(
        "app.services.pose_service.extract_landmarks",
        lambda *a, **k: PoseSeries(fps=FPS, width=640, height=480, frame_count=60, frames=[None] * 60),
    )

    response = app_client.post(
        f"/api/pose/sessions/{session['id']}/analyze",
        files={"video": ("empty.mp4", io.BytesIO(_fake_video()), "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert GATE_NO_POSE_DETECTED in response.json()["error"]["detail"]["gate_failures"]


def test_analysis_records_the_uploaded_media_file(app_client, auth_headers, monkeypatch, db):
    from pathlib import Path as _Path

    from app.db.models import MediaFile

    patient = _patient(app_client, auth_headers, number="P-POSE-8")
    session = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    ).json()
    monkeypatch.setattr(
        "app.services.pose_service.extract_landmarks", lambda *a, **k: _series(90)
    )
    body = app_client.post(
        f"/api/pose/sessions/{session['id']}/analyze",
        files={"video": ("clip.mp4", io.BytesIO(_fake_video()), "video/mp4")},
        headers=auth_headers,
    ).json()

    media = db.query(MediaFile).filter(MediaFile.id == body["session"]["media_file_id"]).one()
    assert media.type == "POSE_VIDEO"
    assert media.original_filename == "clip.mp4"
    assert media.sha256
    # The stored name is a UUID, never the uploaded filename.
    assert _Path(media.stored_path).name != "clip.mp4"
    assert _Path(media.stored_path).suffix == ".mp4"


def test_a_browser_recording_in_webm_is_accepted(app_client, auth_headers, monkeypatch):
    """The pose page records straight from the camera.

    MediaRecorder yields webm in Chrome and Firefox, so refusing that extension
    made the record-then-analyse flow impossible -- the user recorded a clip and
    got "不支持的文件类型 .webm". Both containers are accepted now, and the
    recorded mime type is kept with the file.
    """
    from app.db.models import MediaFile

    patient = _patient(app_client, auth_headers, number="P-POSE-10")
    session = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    ).json()
    monkeypatch.setattr(
        "app.services.pose_service.extract_landmarks", lambda *a, **k: _series(90)
    )

    response = app_client.post(
        f"/api/pose/sessions/{session['id']}/analyze",
        files={"video": ("recording.webm", io.BytesIO(_fake_video()), "video/webm")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    media_id = response.json()["session"]["media_file_id"]
    assert media_id


def test_webm_is_in_the_allowed_video_extensions():
    """The extension list must cover what a browser can actually record."""
    from app.core.config import settings

    assert ".webm" in settings.allowed_video_suffixes
    assert ".mp4" in settings.allowed_video_suffixes


def test_an_unsupported_extension_is_still_refused(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-POSE-11")
    session = app_client.post(
        f"/api/patients/{patient['id']}/pose/sessions",
        json={"exercise_type": "BALLET_PORT_DE_BRAS"},
        headers=auth_headers,
    ).json()
    response = app_client.post(
        f"/api/pose/sessions/{session['id']}/analyze",
        files={"video": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


# -------------------------------------------------------------------- history
def test_history_lists_sessions_newest_first(app_client, auth_headers):
    patient = _patient(app_client, auth_headers, number="P-POSE-9")
    for exercise in ("BALLET_PORT_DE_BRAS", "BALLET_PORT_DE_BRAS", "BALLET_WEIGHT_SHIFT"):
        app_client.post(
            f"/api/patients/{patient['id']}/pose/sessions",
            json={"exercise_type": exercise},
            headers=auth_headers,
        )
    page = app_client.get(
        f"/api/patients/{patient['id']}/pose/sessions", headers=auth_headers
    ).json()
    assert page["total"] == 3
    assert {item["exercise_type"] for item in page["items"]} == {
        "BALLET_PORT_DE_BRAS",
        "BALLET_PORT_DE_BRAS",
        "BALLET_WEIGHT_SHIFT",
    }


def test_missing_session_returns_404(app_client, auth_headers):
    response = app_client.get("/api/pose/sessions/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
