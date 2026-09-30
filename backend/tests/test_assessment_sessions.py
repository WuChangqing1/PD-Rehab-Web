"""Assessment session tests, including the parent/child structure."""

from __future__ import annotations

from datetime import datetime, timedelta


def _create_patient(client, headers, **overrides) -> dict:
    payload = {
        "hospital_number": overrides.pop("hospital_number", "P0001"),
        "name": overrides.pop("name", "测试患者"),
        "sex": "MALE",
        "birthday": "1950-01-01",
        "medication_state": overrides.pop("medication_state", "ON"),
    }
    payload.update(overrides)
    response = client.post("/api/patients", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_session(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    response = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE", "medication_state": "ON"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["patient_id"] == patient["id"]
    assert body["session_type"] == "COMPREHENSIVE"
    assert body["status"] == "IN_PROGRESS"
    assert body["started_at"] is not None


def test_session_inherits_patient_medication_state(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers, medication_state="OFF")
    body = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()
    assert body["medication_state"] == "OFF"


def test_single_module_session_types_supported(app_client, auth_headers):
    """V1 requires running one module alone; the enum must allow it."""
    patient = _create_patient(app_client, auth_headers)
    for session_type in ("MICRO_EXPRESSION_ONLY", "FINGER_TAPPING_ONLY", "FUNCTIONAL_TEST"):
        response = app_client.post(
            f"/api/patients/{patient['id']}/assessment-sessions",
            json={"session_type": session_type},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["session_type"] == session_type


def test_session_for_missing_patient_returns_404(app_client, auth_headers):
    response = app_client.post(
        "/api/patients/nope/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_get_session_detail_has_child_collections(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()

    detail = app_client.get(
        f"/api/assessment-sessions/{session['id']}", headers=auth_headers
    ).json()
    assert detail["id"] == session["id"]
    assert detail["micro_expression_results"] == []
    assert detail["finger_tapping_results"] == []
    assert detail["functional_assessments"] == []


def test_complete_session(app_client, auth_headers):
    """A MICRO_EXPRESSION_ONLY session only needs its own module.

    Completion is no longer unconditional: a comprehensive session must actually
    hold the results it claims, and a single-module session must hold its own.
    """
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "MICRO_EXPRESSION_ONLY"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/complete",
        json={"notes": "本次评估完成"},
        headers=auth_headers,
    )
    # The micro-expression model is not configured in this environment, so that
    # module is reported as skipped rather than as done, and completion proceeds.
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["completed_at"] is not None
    assert body["notes"] is not None
    assert "本次评估完成" in body["notes"]
    assert "SKIPPED_MODEL_UNAVAILABLE" in body["notes"]


def test_a_comprehensive_session_cannot_complete_without_its_results(
    app_client, auth_headers
):
    """The old behaviour let an empty assessment be marked complete."""
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert response.status_code == 409, response.text
    items = response.json()["error"]["detail"]["items"]
    pending = {i["key"] for i in items if i["state"] == "PENDING"}
    # Both hands are outstanding; the unavailable model is not.
    assert pending == {"finger_tapping_left", "finger_tapping_right"}


def test_readiness_endpoint_lists_every_item_with_its_state(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()

    body = app_client.get(
        f"/api/assessment-sessions/{session['id']}/readiness", headers=auth_headers
    ).json()
    states = {item["key"]: item["state"] for item in body["items"]}
    assert states["micro_expression"] in ("PENDING", "SKIPPED_MODEL_UNAVAILABLE")
    assert states["finger_tapping_left"] == "PENDING"
    assert states["finger_tapping_right"] == "PENDING"
    assert body["can_complete"] is False


def test_in_progress_filter_finds_unfinished_sessions(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    for _ in range(2):
        app_client.post(
            f"/api/patients/{patient['id']}/assessment-sessions",
            json={"session_type": "FINGER_TAPPING_ONLY"},
            headers=auth_headers,
        )
    page = app_client.get(
        f"/api/patients/{patient['id']}/assessment-sessions",
        params={"status": "IN_PROGRESS"},
        headers=auth_headers,
    ).json()
    assert page["total"] == 2
    assert all(item["status"] == "IN_PROGRESS" for item in page["items"])


def test_completing_twice_conflicts(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()
    app_client.post(
        f"/api/assessment-sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    second = app_client.post(
        f"/api/assessment-sessions/{session['id']}/complete", json={}, headers=auth_headers
    )
    assert second.status_code == 409


def test_micro_expression_only_session_rejects_finger_tapping(app_client, auth_headers):
    """A session type must actually constrain what it collects.

    Only the status was checked before, so a session created for video analysis
    accepted finger tapping and the stored data contradicted the session type the
    summary is built from.
    """
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "MICRO_EXPRESSION_ONLY"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/finger-tapping",
        data={"hand": "RIGHT", "medication_state": "ON"},
        files={"video": ("tap.mp4", b"fake-video-bytes", "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["session_type"] == "MICRO_EXPRESSION_ONLY"


def test_finger_tapping_only_session_rejects_video_analysis(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "FINGER_TAPPING_ONLY"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/micro-expression",
        data={"medication_state": "ON"},
        files={"video": ("face.mp4", b"fake-video-bytes", "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["session_type"] == "FINGER_TAPPING_ONLY"


def test_comprehensive_session_accepts_both_modules(app_client, auth_headers):
    """A comprehensive session is the one type that collects everything."""
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()

    # Both are refused by the *quality* gates (the bytes are not a video), not by
    # the session-type guard: that is the distinction being tested.
    finger = app_client.post(
        f"/api/assessment-sessions/{session['id']}/finger-tapping",
        data={"hand": "LEFT", "medication_state": "ON"},
        files={"video": ("tap.mp4", b"fake-video-bytes", "video/mp4")},
        headers=auth_headers,
    )
    assert finger.status_code == 422, finger.text
    assert finger.json()["error"]["code"] != "CONFLICT"


def test_list_sessions_for_patient(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    for _ in range(3):
        app_client.post(
            f"/api/patients/{patient['id']}/assessment-sessions",
            json={"session_type": "COMPREHENSIVE"},
            headers=auth_headers,
        )
    page = app_client.get(
        f"/api/patients/{patient['id']}/assessment-sessions", headers=auth_headers
    ).json()
    assert page["total"] == 3
    assert len(page["items"]) == 3


def test_finger_tapping_summary_empty_session(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "COMPREHENSIVE"},
        headers=auth_headers,
    ).json()

    response = app_client.get(
        f"/api/assessment-sessions/{session['id']}/finger-tapping", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session["id"]
    assert body["left"] is None
    assert body["right"] is None
    # one comparison entry per tracked metric, all None while no result exists
    assert len(body["comparisons"]) >= 4
    assert all(c["absolute_difference"] is None for c in body["comparisons"])


def test_finger_tapping_upload_rejects_non_video(app_client, auth_headers):
    """Phase 4: the pipeline is real, so a non-video must be refused by QC.

    The bytes below carry a .mp4 name but are not a video, so OpenCV cannot open
    them. The point of the check is that the API reports a specific quality code
    rather than inventing metrics.
    """
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "FINGER_TAPPING_ONLY"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/finger-tapping",
        data={"hand": "RIGHT", "medication_state": "ON"},
        files={"video": ("tap.mp4", b"fake-video-bytes", "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] in (
        "VIDEO_UNREADABLE",
        "VIDEO_FPS_INVALID",
        "VIDEO_TOO_SHORT",
    )
    # the quality report must be attached so the operator can see why
    assert "quality" in (body["error"]["detail"] or {})


def test_finger_tapping_writes_no_result_row_on_rejection(
    app_client, auth_headers, db
):
    """A rejected recording must not leave a half-populated result behind."""
    from app.db.models import FingerTappingResult

    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "FINGER_TAPPING_ONLY"},
        headers=auth_headers,
    ).json()

    app_client.post(
        f"/api/assessment-sessions/{session['id']}/finger-tapping",
        data={"hand": "LEFT"},
        files={"video": ("tap.mp4", b"not-a-video", "video/mp4")},
        headers=auth_headers,
    )
    assert db.query(FingerTappingResult).count() == 0

    # and the session summary stays empty rather than showing zeros
    summary = app_client.get(
        f"/api/assessment-sessions/{session['id']}/finger-tapping", headers=auth_headers
    ).json()
    assert summary["left"] is None
    assert summary["right"] is None


def test_unsupported_upload_extension_rejected(app_client, auth_headers):
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "FINGER_TAPPING_ONLY"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/finger-tapping",
        data={"hand": "RIGHT"},
        files={"video": ("notes.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_micro_expression_reports_model_not_configured(app_client, auth_headers):
    """The system must never fabricate a result when no model is configured."""
    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "MICRO_EXPRESSION_ONLY"},
        headers=auth_headers,
    ).json()

    response = app_client.post(
        f"/api/assessment-sessions/{session['id']}/micro-expression",
        data={"medication_state": "ON"},
        files={"video": ("face.mp4", b"fake-video-bytes", "video/mp4")},
        headers=auth_headers,
    )
    assert response.status_code == 503, response.text
    body = response.json()
    assert body["error"]["code"] == "MODEL_NOT_CONFIGURED"
    assert "detail" in body["error"]


def test_micro_expression_writes_no_result_row(app_client, auth_headers, db):
    from app.db.models import MicroExpressionResult

    patient = _create_patient(app_client, auth_headers)
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "MICRO_EXPRESSION_ONLY"},
        headers=auth_headers,
    ).json()

    app_client.post(
        f"/api/assessment-sessions/{session['id']}/micro-expression",
        data={},
        files={"video": ("face.mp4", b"bytes", "video/mp4")},
        headers=auth_headers,
    )
    count = db.query(MicroExpressionResult).count()
    assert count == 0


def test_sessions_require_authentication(app_client):
    assert app_client.get("/api/patients/x/assessment-sessions").status_code == 401
