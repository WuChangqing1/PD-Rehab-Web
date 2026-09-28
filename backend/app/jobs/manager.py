"""Minimal in-process job manager for long-running work.

Spec V2 section 49: PENDING / RUNNING / SUCCESS / FAILED with no Redis and no
Celery. Jobs live in memory for the lifetime of the process, which is
sufficient for a single-worker demo deployment. Phase 4+ will move results into
the database so they survive a restart.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.errors import error_body
from app.core.logging import get_logger
from app.db.enums import JobStatus, JobType
from app.jobs.gpu_inference import inference_manager

logger = get_logger(__name__)

_MAX_JOBS = 200


@dataclass
class Job:
    job_id: str
    job_type: str
    status: str = str(JobStatus.PENDING)
    progress: float = 0.0
    result_ref: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in ("created_at", "started_at", "finished_at"):
            value = d.get(key)
            d[key] = value.isoformat() if value else None
        return d


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ create
    def create(self, job_type: JobType | str) -> Job:
        job = Job(job_id=str(uuid.uuid4()), job_type=str(job_type))
        with self._lock:
            self._jobs[job.job_id] = job
            if len(self._jobs) > _MAX_JOBS:
                # Drop the oldest finished jobs first.
                finished = sorted(
                    (j for j in self._jobs.values() if j.finished_at is not None),
                    key=lambda j: j.finished_at or j.created_at,
                )
                for stale in finished[: len(self._jobs) - _MAX_JOBS]:
                    self._jobs.pop(stale.job_id, None)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    # ------------------------------------------------------------------- state
    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in changes.items():
                setattr(job, key, value)

    def run_sync(
        self,
        job_type: JobType | str,
        func: Callable[[], dict[str, Any] | None],
    ) -> Job:
        """Run `func` inline under the single-concurrency inference lock.

        Phase 1 executes synchronously so failures surface immediately; the job
        record keeps the same shape a background execution would produce.
        """
        job = self.create(job_type)
        self._update(job.job_id, status=str(JobStatus.RUNNING),
                     started_at=datetime.now(timezone.utc))
        try:
            with inference_manager.acquire_sync():
                result_ref = func()
        except Exception as exc:  # noqa: BLE001 - converted to the error contract
            code = getattr(exc, "code", "INTERNAL_ERROR")
            message = getattr(exc, "message", None) or str(exc)
            detail = getattr(exc, "detail_payload", None)
            logger.warning("job %s failed: %s %s", job.job_id, code, message)
            self._update(
                job.job_id,
                status=str(JobStatus.FAILED),
                error=error_body(code, message, detail),
                finished_at=datetime.now(timezone.utc),
            )
        else:
            self._update(
                job.job_id,
                status=str(JobStatus.SUCCESS),
                progress=1.0,
                result_ref=result_ref,
                finished_at=datetime.now(timezone.utc),
            )
        job = self.get(job.job_id)
        assert job is not None
        return job


job_manager = JobManager()
