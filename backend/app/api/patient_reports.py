import hashlib
from datetime import date
from fastapi import APIRouter
from fastapi.responses import Response
from app.api.deps import CurrentUser, DbSession
from app.services import audit_service
from app.services.patient_report import render_patient_pdf, report_filename

router = APIRouter(tags=['Patient reports'])


@router.get('/patients/{patient_id}/report.pdf')
def download_report(patient_id: str, db: DbSession, user: CurrentUser,
                    start_date: date | None = None, end_date: date | None = None):
    from app.services.business_export import build_patient_export
    payload = build_patient_export(db, patient_id, user, start_date, end_date, include_attachments=False)
    content = render_patient_pdf(payload)
    digest = hashlib.sha256(content).hexdigest()
    audit_service.record(db, staff_user_id=user.id, action='PATIENT_REPORT_DOWNLOAD',
                         entity_type='patient', entity_id=patient_id,
                         detail={'start_date':str(start_date),'end_date':str(end_date), 'sha256':digest})
    return Response(content,media_type='application/pdf',headers={
        'Content-Disposition':f'attachment; filename="{report_filename(payload)}"',
        'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff','X-Content-SHA256':digest})
