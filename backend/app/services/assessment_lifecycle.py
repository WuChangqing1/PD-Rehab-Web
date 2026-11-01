"""Lease fallback when a browser cannot deliver its final exit request."""
import asyncio
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.base import utcnow
from app.db.models import AssessmentSession
from app.core.errors import APIError
from app.core.logging import get_logger
from app.services import assessment_service,audit_service
logger=get_logger(__name__)
LEASE_SECONDS=90
REAP_INTERVAL_SECONDS=15

def expire_abandoned(db:Session,cutoff)->int:
    ids=list(db.scalars(select(AssessmentSession.id).where(
        AssessmentSession.status=='IN_PROGRESS',AssessmentSession.updated_at<cutoff)))
    removed=0
    for id in ids:
        row=db.get(AssessmentSession,id,populate_existing=True)
        if row is None or row.status!='IN_PROGRESS' or row.updated_at>=cutoff:continue
        try:
            assessment_service.delete_session(db,id,row.patient_id,stale_before=cutoff)
        except APIError as error:
            db.rollback()
            if error.status_code in (404,409):continue
            raise
        audit_service.record(db,staff_user_id=None,action='ASSESSMENT_SESSION_EXPIRED',
                             entity_type='assessment_session',entity_id=id)
        removed+=1
    return removed

def reap():
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        return expire_abandoned(db,utcnow()-timedelta(seconds=LEASE_SECONDS))

async def cleanup_loop():
    while True:
        await asyncio.sleep(REAP_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(reap)
        except Exception:
            logger.exception('Could not remove expired assessment sessions')
