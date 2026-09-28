"""GPU / CPU inference concurrency manager.

Spec V2 section 31: model inference must be single-concurrency so that
multiple requests cannot exhaust GPU memory (or, on a CPU-only server, the
machine's RAM). The limit is applied unconditionally, so local GPU runs and
server CPU runs behave identically.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, contextmanager

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GPUInferenceManager:
    """Serialises inference. Works for both asyncio and worker threads."""

    def __init__(self, concurrency: int | None = None) -> None:
        self.concurrency = max(1, concurrency or settings.gpu_inference_concurrency)
        self._sem = asyncio.Semaphore(self.concurrency)
        self._lock = threading.Lock()
        self._waiting = 0

    @property
    def waiting(self) -> int:
        return self._waiting

    @asynccontextmanager
    async def acquire(self):
        self._waiting += 1
        if self._waiting > 1:
            logger.info("inference queued (waiting=%d)", self._waiting)
        try:
            async with self._sem:
                yield
        finally:
            self._waiting -= 1

    @contextmanager
    def acquire_sync(self):
        """Thread-safe variant for FastAPI BackgroundTasks / worker threads."""
        self._waiting += 1
        try:
            with self._lock:
                yield
        finally:
            self._waiting -= 1


inference_manager = GPUInferenceManager()

__all__ = ["GPUInferenceManager", "inference_manager"]
