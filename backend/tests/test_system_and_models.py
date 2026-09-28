"""Model status and system endpoint tests.

The central guarantee: while no real model exists, the API reports that
honestly and writes no result rows. No mock output, ever.
"""

from __future__ import annotations

from app.ml.registry import ModelRegistry, ModelState, ModelStatus


def test_model_status_serialisation():
    status = ModelStatus(
        name="demo",
        version="1.0",
        state=ModelState.MODEL_NOT_CONFIGURED,
        detail="not configured",
    )
    payload = status.to_dict()
    assert payload["state"] == "MODEL_NOT_CONFIGURED"
    assert payload["is_ready"] is False
    assert payload["loaded_at"] is None


def test_registry_marks_ready_and_stamps_loaded_at():
    registry = ModelRegistry()
    registry.set(ModelStatus(name="m", version="1", state=ModelState.READY))
    stored = registry.get("m")
    assert stored is not None
    assert stored.is_ready
    assert stored.loaded_at is not None


def test_registry_summary_counts():
    registry = ModelRegistry()
    registry.set(ModelStatus(name="a", version="1", state=ModelState.READY))
    registry.set(ModelStatus(name="b", version="1", state=ModelState.MODEL_NOT_CONFIGURED))
    summary = registry.summary()
    assert summary["total"] == 2
    assert summary["ready"] == 1
    assert summary["not_ready"] == 1


def test_system_health_is_public(app_client):
    response = app_client.get("/api/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"]


def test_micro_expression_reports_model_not_configured(app_client):
    """The default deployment has no model directory, so state must be honest."""
    body = app_client.get("/api/system/models").json()
    micro = body["models"]["micro_expression_model"]
    assert micro["state"] == "MODEL_NOT_CONFIGURED"
    assert micro["is_ready"] is False


def test_mock_mode_defaults_off(app_client):
    body = app_client.get("/api/system/models").json()
    assert body["mock_mode"] is False


def test_finger_tapping_reports_unavailable_not_ready(app_client):
    body = app_client.get("/api/system/models").json()
    finger = body["models"]["finger_tapping"]
    assert finger["is_ready"] is False
    assert finger["state"] in ("UNAVAILABLE", "MODEL_NOT_CONFIGURED")
    assert finger["extra"]["pipeline_implemented"] is False
    assert finger["extra"]["severity_model_present"] is False


def test_mediapipe_landmarker_status_is_reported_honestly(app_client):
    body = app_client.get("/api/system/models").json()
    landmarker = body["models"]["mediapipe_hand_landmarker"]
    # present on disk or not, the reported state must match reality
    assert landmarker["extra"]["present"] == (landmarker["state"] == "READY")


def test_pose_reports_not_ready(app_client):
    body = app_client.get("/api/system/models").json()
    pose = body["models"]["mediapipe_pose"]
    assert pose["is_ready"] is False
    assert pose["extra"]["metrics_implemented"] is False


def test_exercises_endpoint_lists_five(app_client):
    body = app_client.get("/api/system/models").json()
    exercises = body["exercises"]
    assert len(exercises) == 5
    keys = {e["key"] for e in exercises}
    assert keys == {
        "MOUNTAIN_ARMS_UP",
        "ARMS_LATERAL_RAISE",
        "SIDE_BEND_STRETCH",
        "SEATED_TRUNK_ROTATION",
        "SEATED_ALTERNATING_ARM_RAISE",
    }


def test_pose_display_scores_are_declared_unavailable(app_client):
    """Scores must not be advertised as available before formulas exist."""
    exercises = app_client.get("/api/system/models").json()["exercises"]
    assert all(e["scores_available"] is False for e in exercises)
    assert all(e["completion_formula"] is None for e in exercises)


def test_gpu_endpoint_reports_torch_state(app_client):
    body = app_client.get("/api/system/gpu").json()
    assert body["gpu_inference_concurrency"] == 1
    assert isinstance(body["torch_installed"], bool)
    if not body["torch_installed"]:
        assert body["cuda_available"] is False
        assert body["driver_note"]


def test_system_info_requires_auth(app_client):
    assert app_client.get("/api/system/info").status_code == 401


def test_system_info_counts(app_client, auth_headers):
    body = app_client.get("/api/system/info", headers=auth_headers).json()
    assert body["counts"]["patients"] == 0
    assert body["mock_mode"] is False
    assert body["python_version"].startswith("3.11")


def test_dashboard_summary(app_client, auth_headers):
    body = app_client.get("/api/system/dashboard", headers=auth_headers).json()
    assert body["counts"]["total_patients"] == 0
    assert body["counts"]["today_assessments"] == 0
    assert body["recent_patients"] == []
    assert "model_status" in body


def test_dashboard_reflects_new_patient(app_client, auth_headers):
    app_client.post(
        "/api/patients",
        json={"hospital_number": "P9001", "name": "看板患者", "sex": "FEMALE"},
        headers=auth_headers,
    )
    body = app_client.get("/api/system/dashboard", headers=auth_headers).json()
    assert body["counts"]["total_patients"] == 1
    assert body["recent_patients"][0]["name"] == "看板患者"


def test_jobs_endpoint_requires_auth(app_client):
    assert app_client.get("/api/jobs").status_code == 401


def test_unknown_job_returns_404(app_client, auth_headers):
    response = app_client.get("/api/jobs/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_medical_disclaimer_present_on_root(app_client):
    body = app_client.get("/").json()
    assert "不能替代专业医生诊断" in body["disclaimer"]
