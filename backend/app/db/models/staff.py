"""staff_users and audit_logs (spec V2 sections 36 and 47)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPk


class StaffUser(Base, UUIDPk, Timestamped):
    __tablename__ = "staff_users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # StaffRole: ADMIN | DOCTOR
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="DOCTOR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="staff_user")


class AuditLog(Base, UUIDPk):
    __tablename__ = "audit_logs"

    staff_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("staff_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    staff_user: Mapped["StaffUser | None"] = relationship(back_populates="audit_logs")
