"""Patient service: CRUD with soft delete and search."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.db.base import utcnow
from app.db.models import (
    AssessmentSession,
    FunctionalAssessment,
    Patient,
    PianoSession,
    PoseSession,
)
from app.schemas.patient import PatientCreate, PatientUpdate


def _get_or_404(db: Session, patient_id: str, *, include_deleted: bool = False) -> Patient:
    stmt = select(Patient).where(Patient.id == patient_id)
    if not include_deleted:
        stmt = stmt.where(Patient.is_deleted.is_(False))
    patient = db.execute(stmt).scalar_one_or_none()
    if patient is None:
        raise not_found("患者不存在或已被删除。", {"patient_id": patient_id})
    return patient


def _assert_hospital_number_free(
    db: Session, hospital_number: str, *, exclude_id: str | None = None
) -> None:
    stmt = select(Patient.id).where(Patient.hospital_number == hospital_number)
    if exclude_id:
        stmt = stmt.where(Patient.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise conflict(
            f"患者编号 {hospital_number} 已存在。",
            {"hospital_number": hospital_number},
        )


def create_patient(db: Session, payload: PatientCreate, *, created_by: str | None = None) -> Patient:
    _assert_hospital_number_free(db, payload.hospital_number)
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: str) -> Patient:
    return _get_or_404(db, patient_id)


def list_patients(
    db: Session,
    *,
    search: str | None = None,
    medication_state: str | None = None,
    affected_side: str | None = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Patient], int]:
    stmt = select(Patient)
    count_stmt = select(func.count()).select_from(Patient)

    conditions = []
    if not include_deleted:
        conditions.append(Patient.is_deleted.is_(False))
    if search:
        like = f"%{search.strip()}%"
        conditions.append(
            or_(
                Patient.name.like(like),
                Patient.hospital_number.like(like),
                Patient.phone.like(like),
            )
        )
    if medication_state:
        conditions.append(Patient.medication_state == medication_state)
    if affected_side:
        conditions.append(Patient.affected_side == affected_side)

    for cond in conditions:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Patient.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.execute(stmt).scalars().all()), total


def update_patient(db: Session, patient_id: str, payload: PatientUpdate) -> Patient:
    patient = _get_or_404(db, patient_id)
    data = payload.model_dump(exclude_unset=True)
    if "hospital_number" in data and data["hospital_number"] != patient.hospital_number:
        _assert_hospital_number_free(db, data["hospital_number"], exclude_id=patient_id)
    for key, value in data.items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient


def soft_delete_patient(db: Session, patient_id: str) -> Patient:
    """Soft delete only: medical history must never be destroyed."""
    patient = _get_or_404(db, patient_id)
    patient.is_deleted = True
    db.commit()
    db.refresh(patient)
    return patient


def restore_patient(db: Session, patient_id: str) -> Patient:
    patient = _get_or_404(db, patient_id, include_deleted=True)
    patient.is_deleted = False
    db.commit()
    db.refresh(patient)
    return patient


# --------------------------------------------------------------- list helpers
def last_activity_map(db: Session, patient_ids: list[str]) -> dict[str, dict[str, datetime | None]]:
    """Latest assessment and training timestamps per patient, in two queries."""
    out: dict[str, dict[str, datetime | None]] = {
        pid: {"last_assessment_at": None, "last_training_at": None} for pid in patient_ids
    }
    if not patient_ids:
        return out

    last_assessment = dict(
        db.execute(
            select(AssessmentSession.patient_id, func.max(AssessmentSession.created_at))
            .where(AssessmentSession.patient_id.in_(patient_ids))
            .group_by(AssessmentSession.patient_id)
        ).all()
    )
    training_rows = db.execute(
        select(PianoSession.patient_id, PianoSession.started_at, PianoSession.completed_at)
        .where(PianoSession.patient_id.in_(patient_ids))
    ).all()
    pose_rows = db.execute(
        select(PoseSession.patient_id, PoseSession.started_at, PoseSession.completed_at)
        .where(PoseSession.patient_id.in_(patient_ids))
    ).all()

    for pid, started, completed in list(training_rows) + list(pose_rows):
        stamp = completed or started
        if stamp is None:
            continue
        current = out.get(pid, {}).get("last_training_at")
        if current is None or stamp > current:
            out[pid]["last_training_at"] = stamp

    functional_rows = db.execute(
        select(FunctionalAssessment.patient_id, func.max(FunctionalAssessment.performed_at))
        .where(FunctionalAssessment.patient_id.in_(patient_ids))
        .group_by(FunctionalAssessment.patient_id)
    ).all()

    for pid in patient_ids:
        out[pid]["last_assessment_at"] = last_assessment.get(pid)
        functional = dict(functional_rows).get(pid)
        if functional is not None:
            current = out[pid]["last_assessment_at"]
            if current is None or functional > current:
                out[pid]["last_assessment_at"] = functional
    return out


def patient_counts(db: Session) -> dict[str, int]:
    """Counts used by the dashboard."""
    total = db.execute(
        select(func.count()).select_from(Patient).where(Patient.is_deleted.is_(False))
    ).scalar_one()
    return {"total_patients": int(total)}


def today_counts(db: Session) -> dict[str, int]:
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    assessments = db.execute(
        select(func.count())
        .select_from(AssessmentSession)
        .where(AssessmentSession.created_at >= today)
    ).scalar_one()

    piano = db.execute(
        select(func.count())
        .select_from(PianoSession)
        .where(PianoSession.started_at.is_not(None), PianoSession.started_at >= today)
    ).scalar_one()
    pose = db.execute(
        select(func.count())
        .select_from(PoseSession)
        .where(PoseSession.started_at.is_not(None), PoseSession.started_at >= today)
    ).scalar_one()

    return {
        "today_assessments": int(assessments),
        "today_trainings": int(piano) + int(pose),
    }


def recent_patients(db: Session, limit: int = 5) -> list[Patient]:
    stmt = (
        select(Patient)
        .where(Patient.is_deleted.is_(False))
        .order_by(Patient.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def recent_assessments(db: Session, limit: int = 5) -> list[AssessmentSession]:
    stmt = select(AssessmentSession).order_by(AssessmentSession.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())
