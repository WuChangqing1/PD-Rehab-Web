"""Job endpoints (spec V2 section 48)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.errors import not_found, forbidden
from sqlalchemy import select
from app.db.models import Patient
from app.services import integration_access as access
from app.jobs.manager import job_manager

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}", summary="查询长任务状态")
def get_job(job_id: str, user: CurrentUser, db: DbSession) -> dict:
    job = job_manager.get(job_id)
    if job is None:
        raise not_found("任务不存在或已过期。", {"job_id": job_id})
    if user.role!='ADMIN':
        if not job.patient_id:raise forbidden("任务缺少患者授权范围。")
        access.patient(db,job.patient_id,user)
    return job.to_dict()


@router.get("", summary="任务列表（调试用）")
def list_jobs(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    jobs=job_manager.list()
    if user.role!='ADMIN':
        allowed=set(db.scalars(select(Patient.id).where(access.scope(db,user))))
        jobs=[j for j in jobs if j.patient_id in allowed]
    return [j.to_dict() for j in jobs[:limit]]
