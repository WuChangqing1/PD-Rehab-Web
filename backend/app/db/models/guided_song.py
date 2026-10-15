"""Isolated elastic guided-song sessions; never mixed with fixed-beat scores."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPk, utcnow


class GuidedSongSession(Base, UUIDPk):
    __tablename__ = 'guided_song_sessions'
    __table_args__ = (UniqueConstraint('owner_id', 'client_request_id'),)
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('staff_users.id'), index=True)
    client_request_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default='ACTIVE')
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    events: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    audio: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    audio_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_simulation(self):
        return self.config.get('is_simulation', False)
