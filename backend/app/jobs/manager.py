"""Single-worker job manager with atomic private metadata snapshots.

Domain results remain in the existing database. Snapshots make status and
result references survive restart; interrupted work is explicitly failed.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
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
    patient_id: str | None = None
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
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self.storage_dir = Path(storage_dir) if storage_dir is not None else settings.output_path / 'jobs'
        self._restore()

    def _save(self, job: Job) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        destination = self.storage_dir / (str(uuid.UUID(job.job_id)) + '.json')
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.tmp',
                                             dir=self.storage_dir, delete=False) as target:
                name = target.name
                json.dump(job.to_dict(), target, ensure_ascii=False, allow_nan=False)
                target.flush()
                os.fsync(target.fileno())
            os.replace(name, destination)
        finally:
            if name and Path(name).exists():
                Path(name).unlink()

    def _restore(self) -> None:
        if not self.storage_dir.is_dir():
            return
        for path in self.storage_dir.glob('*.json'):
            try:
                # Ignore foreign names, symlinks and partial/corrupt snapshots.
                identifier = str(uuid.UUID(path.stem))
                if path.name != identifier + '.json' or path.is_symlink():
                    continue
                data = json.loads(path.read_text(encoding='utf-8'))
                if data.get('job_id') != identifier:
                    continue
                for key in ('created_at', 'started_at', 'finished_at'):
                    data[key] = datetime.fromisoformat(data[key]) if data.get(key) else None
                    if data[key] and data[key].tzinfo is None:
                        data[key] = data[key].replace(tzinfo=timezone.utc)
                if data['created_at'] is None:
                    continue
                job = Job(**data)
                if job.status in (str(JobStatus.PENDING), str(JobStatus.RUNNING)):
                    job.status = str(JobStatus.FAILED)
                    job.error = error_body('TASK_INTERRUPTED', 'Service restarted; submit the task again.')
                    job.finished_at = datetime.now(timezone.utc)
                    self._save(job)
                self._jobs[identifier] = job
            except (OSError, ValueError, TypeError, KeyError):
                logger.warning('Skipping invalid job metadata: %s', path.name)
        self._prune()

    def _prune(self) -> None:
        finished = sorted((j for j in self._jobs.values() if j.finished_at is not None),
                          key=lambda j: j.finished_at or j.created_at)
        for stale in finished[:max(0, len(self._jobs) - _MAX_JOBS)]:
            # Only files corresponding to our successfully loaded job UUIDs.
            (self.storage_dir / (stale.job_id + '.json')).unlink(missing_ok=True)
            self._jobs.pop(stale.job_id, None)

    # ------------------------------------------------------------------ create
    def create(self, job_type: JobType | str, *, patient_id: str | None = None) -> Job:
        job = Job(job_id=str(uuid.uuid4()), job_type=str(job_type), patient_id=patient_id)
        with self._lock:
            self._save(job)
            self._jobs[job.job_id] = job
            self._prune()
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
            updated = replace(job, **changes)
            self._save(updated)
            # Preserve existing references held by synchronous callers.
            for key, value in changes.items():
                setattr(job, key, value)

    def run_sync(
        self,
        job_type: JobType | str,
        func: Callable[[], dict[str, Any] | None],
        *, patient_id: str | None = None,
    ) -> Job:
        """Run `func` inline under the single-concurrency inference lock.

        Phase 1 executes synchronously so failures surface immediately; the job
        record keeps the same shape a background execution would produce.
        """
        job = self.create(job_type,patient_id=patient_id)
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


# Tests must never restore or write real deployment job snapshots.
_test_directory = tempfile.TemporaryDirectory(prefix='pd-test-jobs-') if os.environ.get('APP_ENV') == 'test' else None
job_manager = JobManager(Path(_test_directory.name) if _test_directory else None)
