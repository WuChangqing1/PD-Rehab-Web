"""Audit log service.

Records who did what. Failures here must never break the main request, so the
write is best-effort and swallowed after logging.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import AuditLog

logger = get_logger(__name__)


def record(
    db: Session,
    *,
    staff_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    try:
        entry = AuditLog(
            staff_user_id=staff_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
            created_at=utcnow(),
        )
        db.add(entry)
        if commit:
            db.commit()
    except Exception as exc:  # noqa: BLE001 - auditing must not break the request
        logger.warning("audit log write failed: %s: %s", type(exc).__name__, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
