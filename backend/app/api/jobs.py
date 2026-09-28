"""Job endpoints (spec V2 section 48)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.core.errors import not_found
from app.jobs.manager import job_manager

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}", summary="查询长任务状态")
def get_job(job_id: str, user: CurrentUser) -> dict:
    job = job_manager.get(job_id)
    if job is None:
        raise not_found("任务不存在或已过期。", {"job_id": job_id})
    return job.to_dict()


@router.get("", summary="任务列表（调试用）")
def list_jobs(
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    return [j.to_dict() for j in job_manager.list()[:limit]]
