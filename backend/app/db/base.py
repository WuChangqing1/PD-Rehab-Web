"""Declarative base and shared column helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Timezone-aware UTC now (naive-UTC storage keeps SQLite/MySQL portable)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class UUIDPk:
    """Mixin: UUID string primary key."""

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid, sort_order=-100
    )


class Timestamped:
    """Mixin: created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False, sort_order=101
    )
