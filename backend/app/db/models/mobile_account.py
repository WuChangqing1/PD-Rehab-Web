"""Patient identities use the existing user PK for legacy record ownership FKs.

PATIENT is never a staff permission. The one-to-one profile and revocable
sessions below are checked before any mobile token can reach integration APIs.
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPk, Timestamped


class MobileAccount(Base, Timestamped):
    __tablename__ = 'mobile_accounts'
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('staff_users.id'), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey('patients.id'), unique=True, nullable=False)
    recovery_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sync_consent_version: Mapped[str] = mapped_column(String(40), nullable=False)


class MobileSession(Base, UUIDPk, Timestamped):
    __tablename__ = 'mobile_sessions'
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('mobile_accounts.user_id'), index=True, nullable=False)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    previous_refresh_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
