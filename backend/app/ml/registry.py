"""Model registry: one place that knows which models exist and whether they work.

The dashboard and /api/system/models read from here. A model that is not
configured reports MODEL_NOT_CONFIGURED; it is never reported as ready and the
API never substitutes mock output for it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ModelState(StrEnum):
    """Model lifecycle states (docs/model_integration.md section 1.3)."""

    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    LOADING = "LOADING"
    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"
    LOAD_FAILED = "LOAD_FAILED"


@dataclass
class ModelStatus:
    name: str
    version: str
    state: ModelState
    device: str | None = None
    detail: str | None = None
    loaded_at: datetime | None = None
    # Extra facts worth showing on /system/model-status, e.g. file paths or
    # the reason a component is missing. Never used to imply availability.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.state is ModelState.READY

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = str(self.state)
        d["is_ready"] = self.is_ready
        d["loaded_at"] = self.loaded_at.isoformat() if self.loaded_at else None
        return d


class ModelRegistry:
    """Holds the current status of every model the platform depends on."""

    def __init__(self) -> None:
        self._statuses: dict[str, ModelStatus] = {}

    def set(self, status: ModelStatus) -> None:
        if status.state is ModelState.READY and status.loaded_at is None:
            status.loaded_at = datetime.now(timezone.utc)
        self._statuses[status.name] = status

    def get(self, name: str) -> ModelStatus | None:
        return self._statuses.get(name)

    def all(self) -> list[ModelStatus]:
        return list(self._statuses.values())

    def to_dict(self) -> dict[str, Any]:
        return {name: st.to_dict() for name, st in self._statuses.items()}

    def summary(self) -> dict[str, Any]:
        """Compact view for the dashboard."""
        items = self.all()
        return {
            "total": len(items),
            "ready": sum(1 for s in items if s.is_ready),
            "not_ready": sum(1 for s in items if not s.is_ready),
            "models": [
                {
                    "name": s.name,
                    "version": s.version,
                    "state": str(s.state),
                    "device": s.device,
                    "is_ready": s.is_ready,
                }
                for s in items
            ],
        }


registry = ModelRegistry()
