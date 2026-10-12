"""Uploaded clips must carry the provenance the caller declared.

WHY THIS EXISTS
===============
The finger-tapping upload path could only ever produce a row claiming to be a real
patient measurement. The service hardcoded `input_source="HUMAN_KEYBOARD"`, and the
comment beside it warned against uploading test fixtures -- because such a row would
be indistinguishable from real data -- while offering no way to declare anything
else. Testing the flow meant falsifying the record.

The fix had two halves, and the first attempt at it was wrong in a way that reading
the diff would not have shown: adding the field to `FingerTappingAnalyzeRequest`
changed nothing, because the route reads the multipart body through individual
`Form(...)` parameters and builds the payload by hand. The model accepted the field,
defaulted it, and the route never passed it -- so the upload was still recorded as
HUMAN_KEYBOARD no matter what the client sent. That is the same silent provenance
failure, reproduced one layer up.

It was caught by uploading a real clip twice, once with each value, and reading the
rows back. These tests do the same thing, so the next person to add a form field
finds out immediately rather than in production.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "finger_tapping_sample.mp4"


def _upload(app_client, auth_headers, session_id: str, *, input_source: str | None):
    """Upload the sample clip, optionally declaring where it came from."""
    data = {"hand": "RIGHT", "medication_state": "UNKNOWN"}
    if input_source is not None:
        data["input_source"] = input_source
    with FIXTURE.open("rb") as handle:
        return app_client.post(
            f"/api/assessment-sessions/{session_id}/finger-tapping",
            data=data,
            files={"video": ("sample.mp4", handle, "video/mp4")},
            headers=auth_headers,
        )


def _session(app_client, auth_headers):
    response = app_client.post(
        "/api/patients",
        json={"hospital_number": "P-PROV-UP", "name": "上传来源患者", "sex": "MALE"},
        headers=auth_headers,
    )
    patient = response.json()
    response = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "FINGER_TAPPING_ONLY"},
        headers=auth_headers,
    )
    return response.json()["id"]


def test_declared_selftest_source_is_stored(app_client, auth_headers):
    """The reported defect: a declared value must survive the upload."""
    session_id = _session(app_client, auth_headers)
    response = _upload(app_client, auth_headers, session_id, input_source="SYNTHETIC_SELFTEST")
    assert response.status_code == 200, response.text

    response = app_client.get(
        f"/api/assessment-sessions/{session_id}/finger-tapping", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    right = body.get("right") or {}
    assert right.get("input_source") == "SYNTHETIC_SELFTEST", (
        "the upload was recorded as something other than what the caller declared: "
        f"{right.get('input_source')!r}. A form field that the route does not bind "
        "is silently ignored."
    )


def test_omitting_the_source_still_means_a_person(app_client, auth_headers):
    """The default must not change, so existing clients are unaffected."""
    session_id = _session(app_client, auth_headers)
    response = _upload(app_client, auth_headers, session_id, input_source=None)
    assert response.status_code == 200, response.text

    response = app_client.get(
        f"/api/assessment-sessions/{session_id}/finger-tapping", headers=auth_headers
    )
    right = response.json().get("right") or {}
    assert right.get("input_source") == "HUMAN_KEYBOARD"


def test_an_unknown_source_is_rejected_rather_than_coerced(app_client, auth_headers):
    """A typo must not quietly become a measurement."""
    session_id = _session(app_client, auth_headers)
    response = _upload(app_client, auth_headers, session_id, input_source="ROBOT")
    assert response.status_code == 422, response.text


def test_every_form_field_of_the_upload_route_reaches_the_payload():
    """Guard the class of bug, not just this instance.

    The handler binds multipart fields individually and assembles the payload by
    hand, so a field can exist on the model, be documented, be sent by the client,
    and still never arrive. This asserts the two lists agree.
    """
    import inspect
    import re

    from app.api import assessment_sessions
    from app.schemas.assessment import FingerTappingAnalyzeRequest

    source = inspect.getsource(assessment_sessions.analyze_finger_tapping)

    # Form fields the client can send.
    form_fields = set(re.findall(r"^\s*(\w+):\s*[\w\.\[\]]+\s*=\s*Form\(", source, re.M))
    assert form_fields, "expected to find the route's Form fields"

    # Fields the handler forwards into the payload it builds.
    forwarded = set(re.findall(r"payload\s*=\s*FingerTappingAnalyzeRequest\((.*?)\)", source, re.S))
    forwarded_text = " ".join(forwarded)

    model_fields = set(FingerTappingAnalyzeRequest.model_fields)
    ignored = {"session_id", "db", "user", "video"}

    for field in sorted(form_fields - ignored):
        assert field in model_fields, f"{field} is bound but not on the request model"
        assert re.search(rf"\b{field}\s*=", forwarded_text), (
            f"the route binds a `{field}` form field but never passes it into "
            "FingerTappingAnalyzeRequest, so it is silently discarded -- which is "
            "exactly how a declared provenance became a hardcoded human measurement"
        )
