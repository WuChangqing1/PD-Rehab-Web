"""Pending applications do not create authenticated accounts."""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPk, Timestamped

class StaffApplication(Base, UUIDPk, Timestamped):
    __tablename__ = 'staff_applications'
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='PENDING', nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('staff_users.id'))
    user_id: Mapped[str | None] = mapped_column(ForeignKey('staff_users.id'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
