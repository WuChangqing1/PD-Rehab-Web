"""Patient CRUD, soft delete and search tests."""

from __future__ import annotations

from datetime import date


def test_create_patient(app_client, auth_headers, patient_payload):
    response = app_client.post("/api/patients", json=patient_payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == patient_payload["name"]
    assert body["hospital_number"] == "P0001"
    assert body["medication_state"] == "ON"
    assert body["is_deleted"] is False
    assert body["id"]


def test_age_is_derived_from_birthday(app_client, auth_headers, patient_payload):
    body = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()
    expected = date.today().year - 1955 - (
        (date.today().month, date.today().day) < (3, 12)
    )
    assert body["age"] == expected


def test_duplicate_hospital_number_conflicts(app_client, auth_headers, patient_payload):
    app_client.post("/api/patients", json=patient_payload, headers=auth_headers)
    response = app_client.post("/api/patients", json=patient_payload, headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_get_patient(app_client, auth_headers, patient_payload):
    created = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()
    response = app_client.get(f"/api/patients/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_patient_returns_unified_404(app_client, auth_headers):
    response = app_client.get("/api/patients/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_update_patient(app_client, auth_headers, patient_payload):
    created = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()
    response = app_client.patch(
        f"/api/patients/{created['id']}",
        json={"medication_state": "OFF", "doctor_notes": "复诊"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["medication_state"] == "OFF"
    assert body["doctor_notes"] == "复诊"
    # untouched fields survive a PATCH
    assert body["name"] == patient_payload["name"]


def test_update_to_existing_hospital_number_conflicts(
    app_client, auth_headers, patient_payload
):
    first = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()
    second_payload = dict(patient_payload, hospital_number="P0002", name="李四（虚拟）")
    second = app_client.post(
        "/api/patients", json=second_payload, headers=auth_headers
    ).json()

    response = app_client.patch(
        f"/api/patients/{second['id']}",
        json={"hospital_number": first["hospital_number"]},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_soft_delete_hides_patient_but_keeps_row(
    app_client, auth_headers, patient_payload, db
):
    from app.db.models import Patient

    created = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()

    response = app_client.delete(f"/api/patients/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_deleted"] is True

    # hidden from normal reads
    assert app_client.get(f"/api/patients/{created['id']}", headers=auth_headers).status_code == 404

    # but the row still exists
    row = db.get(Patient, created["id"])
    assert row is not None
    assert row.is_deleted is True


def test_restore_patient(app_client, auth_headers, patient_payload):
    created = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()
    app_client.delete(f"/api/patients/{created['id']}", headers=auth_headers)
    response = app_client.post(
        f"/api/patients/{created['id']}/restore", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["is_deleted"] is False


def test_list_patients_pagination_and_search(app_client, auth_headers, patient_payload):
    for index in range(5):
        payload = dict(
            patient_payload,
            hospital_number=f"P10{index:02d}",
            name=f"患者{index}号",
        )
        assert (
            app_client.post("/api/patients", json=payload, headers=auth_headers).status_code
            == 201
        )

    page = app_client.get(
        "/api/patients", params={"page": 1, "page_size": 2}, headers=auth_headers
    ).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["page"] == 1

    found = app_client.get(
        "/api/patients", params={"q": "患者3"}, headers=auth_headers
    ).json()
    assert found["total"] == 1
    assert found["items"][0]["name"] == "患者3号"

    by_number = app_client.get(
        "/api/patients", params={"q": "P1001"}, headers=auth_headers
    ).json()
    assert by_number["total"] == 1


def test_list_excludes_soft_deleted_by_default(
    app_client, auth_headers, patient_payload
):
    created = app_client.post(
        "/api/patients", json=patient_payload, headers=auth_headers
    ).json()
    app_client.delete(f"/api/patients/{created['id']}", headers=auth_headers)

    visible = app_client.get("/api/patients", headers=auth_headers).json()
    assert visible["total"] == 0

    everything = app_client.get(
        "/api/patients", params={"include_deleted": True}, headers=auth_headers
    ).json()
    assert everything["total"] == 1


def test_list_filter_by_medication_state(app_client, auth_headers, patient_payload):
    app_client.post("/api/patients", json=patient_payload, headers=auth_headers)
    app_client.post(
        "/api/patients",
        json=dict(patient_payload, hospital_number="P0009", medication_state="OFF"),
        headers=auth_headers,
    )

    on_only = app_client.get(
        "/api/patients", params={"medication_state": "ON"}, headers=auth_headers
    ).json()
    assert on_only["total"] == 1
    assert on_only["items"][0]["medication_state"] == "ON"


def test_patient_list_item_shape(app_client, auth_headers, patient_payload):
    app_client.post("/api/patients", json=patient_payload, headers=auth_headers)
    item = app_client.get("/api/patients", headers=auth_headers).json()["items"][0]
    for key in (
        "id",
        "hospital_number",
        "name",
        "sex",
        "age",
        "affected_side",
        "dominant_hand",
        "disease_duration_years",
        "medication_state",
        "last_assessment_at",
        "last_training_at",
    ):
        assert key in item


def test_patients_require_authentication(app_client):
    assert app_client.get("/api/patients").status_code == 401


def test_future_birthday_is_rejected(app_client, auth_headers, patient_payload):
    payload = dict(patient_payload, birthday="2999-01-01")
    response = app_client.post("/api/patients", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_required_fields_are_validated(app_client, auth_headers):
    response = app_client.post("/api/patients", json={"name": "无编号"}, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
