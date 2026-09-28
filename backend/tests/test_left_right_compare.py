"""Left/right comparison tests.

Uses real FingerTappingResult rows because the comparison runs on stored data.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.models import AssessmentSession, FingerTappingResult, Patient
from app.services.assessment_service import compare_left_right


def _patient(db) -> Patient:
    patient = Patient(
        hospital_number="P-LR-1",
        name="Left right test patient",
        sex="UNKNOWN",
        medication_state="ON",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _session(db, patient: Patient) -> AssessmentSession:
    session = AssessmentSession(
        patient_id=patient.id,
        session_type="FINGER_TAPPING_ONLY",
        medication_state="ON",
        status="IN_PROGRESS",
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _result(db, session: AssessmentSession, hand: str, **metrics) -> FingerTappingResult:
    row = FingerTappingResult(
        assessment_session_id=session.id,
        hand=hand,
        feature_schema_version="1.0",
        **metrics,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _all(db, session):
    return (
        db.query(FingerTappingResult)
        .filter(FingerTappingResult.assessment_session_id == session.id)
        .all()
    )


def test_comparison_is_left_minus_right(db):
    patient = _patient(db)
    session = _session(db, patient)
    _result(db, session, "LEFT", avg_amplitude=0.80, avg_speed=1.20,
            tapping_frequency=3.0, cycle_cv=0.20)
    _result(db, session, "RIGHT", avg_amplitude=0.50, avg_speed=1.00,
            tapping_frequency=3.5, cycle_cv=0.30)

    comparisons = {c.metric: c for c in compare_left_right(_all(db, session))}

    assert comparisons["avg_amplitude"].absolute_difference == pytest.approx(0.30)
    assert comparisons["avg_speed"].absolute_difference == pytest.approx(0.20)
    assert comparisons["tapping_frequency"].absolute_difference == pytest.approx(-0.5)
    assert comparisons["cycle_cv"].absolute_difference == pytest.approx(-0.10)


def test_asymmetry_ratio_is_computed(db):
    patient = _patient(db)
    session = _session(db, patient)
    _result(db, session, "LEFT", avg_amplitude=1.0)
    _result(db, session, "RIGHT", avg_amplitude=0.5)

    comparison = next(
        c for c in compare_left_right(_all(db, session)) if c.metric == "avg_amplitude"
    )
    # (1.0 - 0.5) / 0.75
    assert comparison.asymmetry_ratio == pytest.approx(0.5 / 0.75)


def test_missing_side_yields_none_not_zero(db):
    """A one-handed session must not look like a perfect match."""
    patient = _patient(db)
    session = _session(db, patient)
    _result(db, session, "LEFT", avg_amplitude=0.75)

    comparisons = compare_left_right(_all(db, session))
    amplitude = next(c for c in comparisons if c.metric == "avg_amplitude")
    assert amplitude.left == pytest.approx(0.75)
    assert amplitude.right is None
    assert amplitude.absolute_difference is None
    assert amplitude.asymmetry_ratio is None


def test_empty_session_gives_all_none(db):
    patient = _patient(db)
    session = _session(db, patient)
    comparisons = compare_left_right(_all(db, session))
    assert comparisons
    assert all(c.left is None and c.right is None for c in comparisons)
    assert all(c.absolute_difference is None for c in comparisons)


def test_newest_result_wins_when_a_hand_repeats(db):
    patient = _patient(db)
    session = _session(db, patient)
    older = _result(db, session, "LEFT", avg_amplitude=0.10)
    newer = _result(db, session, "LEFT", avg_amplitude=0.90)
    newer.created_at = older.created_at + timedelta(seconds=5)
    db.commit()
    _result(db, session, "RIGHT", avg_amplitude=0.50)

    comparison = next(
        c for c in compare_left_right(_all(db, session)) if c.metric == "avg_amplitude"
    )
    assert comparison.left == pytest.approx(0.90)


def test_comparison_covers_the_required_metrics(db):
    """spec V2 section 13 requires at least these four pairings."""
    patient = _patient(db)
    session = _session(db, patient)
    metrics = {c.metric for c in compare_left_right(_all(db, session))}
    assert {"avg_amplitude", "avg_speed", "tapping_frequency", "cycle_cv"} <= metrics


def test_genuine_zero_difference_is_preserved(db):
    patient = _patient(db)
    session = _session(db, patient)
    _result(db, session, "LEFT", avg_amplitude=0.60)
    _result(db, session, "RIGHT", avg_amplitude=0.60)
    comparison = next(
        c for c in compare_left_right(_all(db, session)) if c.metric == "avg_amplitude"
    )
    assert comparison.absolute_difference == 0.0


def test_comparison_via_api_after_session_creation(app_client, auth_headers):
    """The API path must expose the same empty-but-well-formed summary."""
    patient = app_client.post(
        "/api/patients",
        json={"hospital_number": "P-LR-2", "name": "API compare patient"},
        headers=auth_headers,
    ).json()
    session = app_client.post(
        f"/api/patients/{patient['id']}/assessment-sessions",
        json={"session_type": "FINGER_TAPPING_ONLY"},
        headers=auth_headers,
    ).json()

    body = app_client.get(
        f"/api/assessment-sessions/{session['id']}/finger-tapping", headers=auth_headers
    ).json()
    assert {c["metric"] for c in body["comparisons"]} >= {
        "avg_amplitude",
        "avg_speed",
        "tapping_frequency",
        "cycle_cv",
    }
    assert body["left"] is None and body["right"] is None
