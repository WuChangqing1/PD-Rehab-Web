"""Authorized patient JSON/CSV downloads, generated in memory and never public."""
from datetime import date
import hashlib
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import CurrentUser, DbSession
from app.services import audit_service
from app.services.business_export import build_patient_export, canonical_bytes, csv_bytes

router = APIRouter(prefix='/business-exports', tags=['Business exports'])


@router.get('/patients/{patient_id}')
def export_patient(patient_id: str, db: DbSession, user: CurrentUser,
                   format: Literal['json', 'csv'] = 'json',
                   start_date: date | None = None, end_date: date | None = None):
    payload = build_patient_export(db, patient_id, user, start_date, end_date)
    content = canonical_bytes(payload) if format == 'json' else csv_bytes(payload)
    digest = hashlib.sha256(content).hexdigest()
    audit_service.record(db, staff_user_id=user.id, action='BUSINESS_EXPORT', entity_type='patient',
                         entity_id=patient_id, detail={'format':format, 'start_date':str(start_date) if start_date else None,
                         'end_date':str(end_date) if end_date else None, 'sha256':digest, 'counts':payload['integrity']['counts']})
    # UUID from authorized DB row, rather than caller-controlled filename text.
    filename = f"patient-{payload['patient']['id']}-{start_date or 'all'}-{end_date or 'all'}.{format}"
    return Response(content=content, media_type='application/json' if format == 'json' else 'text/csv; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="{filename}"',
                             'Cache-Control':'private, no-store', 'X-Content-SHA256':digest,
                             'X-Content-Type-Options':'nosniff'})


@router.get('/administration')
def export_administration(db: DbSession, user: CurrentUser, format: Literal['json','csv'] = 'json'):
    from app.services.business_export import build_administration_export
    payload = build_administration_export(db, user)
    content = canonical_bytes(payload) if format == 'json' else csv_bytes(payload)
    digest = hashlib.sha256(content).hexdigest()
    audit_service.record(db, staff_user_id=user.id, action='BUSINESS_EXPORT', entity_type='administration',
                         detail={'format':format, 'sha256':digest, 'counts':payload['integrity']['counts']})
    return Response(content, media_type='application/json' if format == 'json' else 'text/csv; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="administration.{format}"',
                             'Cache-Control':'private, no-store', 'X-Content-SHA256':digest,
                             'X-Content-Type-Options':'nosniff'})
