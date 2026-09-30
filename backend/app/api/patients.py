"""Patient endpoints (spec V2 section 48).

Response shapes are declared with explicit response_model values so OpenAPI and
the frontend types stay in sync.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page, PageParams
from app.schemas.patient import (
    PatientCreate,
    PatientListItem,
    PatientRead,
    PatientUpdate,
)
from app.services import audit_service, patient_service

router = APIRouter(prefix="/patients", tags=["Patients"])


def _to_list_item(patient, activity: dict) -> PatientListItem:
    return PatientListItem(
        id=patient.id,
        hospital_number=patient.hospital_number,
        name=patient.name,
        sex=patient.sex,
        age=patient.age,
        affected_side=patient.affected_side,
        dominant_hand=patient.dominant_hand,
        disease_duration_years=patient.disease_duration_years,
        medication_state=patient.medication_state,
        # Needed by the list UI: without it a soft-deleted patient looked
        # identical to an active one, and the restore endpoint that has existed
        # since Phase 1 had no way to be reached.
        is_deleted=bool(patient.is_deleted),
        last_assessment_at=activity.get("last_assessment_at"),
        last_training_at=activity.get("last_training_at"),
    )


@router.get("", response_model=Page[PatientListItem], summary="患者列表")
def list_patients(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(None, description="按姓名 / 患者编号 / 电话模糊搜索"),
    medication_state: str | None = Query(None, pattern="^(ON|OFF|UNKNOWN)$"),
    affected_side: str | None = Query(None, pattern="^(LEFT|RIGHT|BILATERAL|UNKNOWN)$"),
    include_deleted: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Page[PatientListItem]:
    params = PageParams(page=page, page_size=page_size)
    patients, total = patient_service.list_patients(
        db,
        search=q,
        medication_state=medication_state,
        affected_side=affected_side,
        include_deleted=include_deleted,
        page=params.page,
        page_size=params.page_size,
    )
    activity = patient_service.last_activity_map(db, [p.id for p in patients])
    return Page[PatientListItem](
        items=[_to_list_item(p, activity.get(p.id, {})) for p in patients],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="新增患者",
)
def create_patient(payload: PatientCreate, db: DbSession, user: CurrentUser) -> PatientRead:
    patient = patient_service.create_patient(db, payload, created_by=user.id)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PATIENT_CREATE",
        entity_type="patient",
        entity_id=patient.id,
        detail={"hospital_number": patient.hospital_number, "name": patient.name},
    )
    return PatientRead.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientRead, summary="患者详情")
def get_patient(patient_id: str, db: DbSession, user: CurrentUser) -> PatientRead:
    return PatientRead.model_validate(patient_service.get_patient(db, patient_id))


@router.patch("/{patient_id}", response_model=PatientRead, summary="编辑患者")
def update_patient(
    patient_id: str, payload: PatientUpdate, db: DbSession, user: CurrentUser
) -> PatientRead:
    patient = patient_service.update_patient(db, patient_id, payload)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PATIENT_UPDATE",
        entity_type="patient",
        entity_id=patient.id,
        detail={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return PatientRead.model_validate(patient)


@router.delete("/{patient_id}", response_model=PatientRead, summary="软删除患者")
def delete_patient(patient_id: str, db: DbSession, user: CurrentUser) -> PatientRead:
    """Soft delete only. Historical medical records are never destroyed."""
    patient = patient_service.soft_delete_patient(db, patient_id)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PATIENT_SOFT_DELETE",
        entity_type="patient",
        entity_id=patient.id,
    )
    return PatientRead.model_validate(patient)


@router.post("/{patient_id}/restore", response_model=PatientRead, summary="恢复患者")
def restore_patient(patient_id: str, db: DbSession, user: CurrentUser) -> PatientRead:
    patient = patient_service.restore_patient(db, patient_id)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="PATIENT_RESTORE",
        entity_type="patient",
        entity_id=patient.id,
    )
    return PatientRead.model_validate(patient)
