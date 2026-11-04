"""Training-linked recording parents; originals remain immutable."""
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPk, Timestamped


class FaceRecording(Base, UUIDPk, Timestamped):
    __tablename__ = 'face_recordings'
    __table_args__ = (UniqueConstraint('device_id', 'client_capture_id', name='uq_face_capture_source'),)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey('patients.id'), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(36), ForeignKey('staff_users.id'), nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    local_profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_capture_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_record_id: Mapped[str] = mapped_column(String(36), ForeignKey('external_practice_records.id'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default='UPLOADING', nullable=False, index=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
