"""External identities and single-use, purpose/session-bound login challenges."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPk, Timestamped


class MobileIdentity(Base, UUIDPk, Timestamped):
    __tablename__ = 'mobile_identities'
    __table_args__ = (UniqueConstraint('provider', 'app_id', 'subject', name='uq_mobile_identity_subject'),
                      UniqueConstraint('user_id', 'provider', name='uq_mobile_identity_user_provider'))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('mobile_accounts.user_id'), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    app_id: Mapped[str] = mapped_column(String(64), default='')
    subject: Mapped[str] = mapped_column(String(128))


class MobileLoginChallenge(Base, UUIDPk, Timestamped):
    __tablename__ = 'mobile_login_challenges'
    provider: Mapped[str] = mapped_column(String(16))
    purpose: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(128), default='')
    state_hash: Mapped[str] = mapped_column(String(64), default='')
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('mobile_accounts.user_id'))
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('mobile_sessions.id'))
    status: Mapped[str] = mapped_column(String(16), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class MobileAuthLimit(Base):
    __tablename__ = 'mobile_auth_limits'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    resets_at: Mapped[datetime] = mapped_column(DateTime, index=True)
