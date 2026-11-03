"""Cross-client synchronization, bindings and asynchronous face jobs.

The Flutter source records remain immutable. No reinterpretation of their
validated metrics is performed on ingestion.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPk, Timestamped, utcnow


class DevicePatientLink(Base, UUIDPk, Timestamped):
    __tablename__ = "device_patient_links"
    __table_args__ = (UniqueConstraint("device_id", "local_profile_id", name="uq_device_profile"),)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    local_profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bound_by: Mapped[str] = mapped_column(String(36), ForeignKey("staff_users.id"), nullable=False)


class ExternalPracticeRecord(Base, UUIDPk):
    __tablename__ = "external_practice_records"
    __table_args__ = (UniqueConstraint("device_id", "source_record_id", "record_type", name="uq_external_record_source"),)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff_users.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    local_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    task_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metric_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origin: Mapped[str] = mapped_column(String(40), nullable=False, default="PianoForParkinson")
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


class MobileFaceJob(Base, UUIDPk, Timestamped):
    __tablename__ = "mobile_face_jobs"
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff_users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="REVIEW_REQUIRED")
    stored_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assessment_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    local_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    indices_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidates_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExpertChatTurn(Base, UUIDPk):
    __tablename__ = "expert_chat_turns"
    operator_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff_users.id"), nullable=False, index=True)
    patient_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("patients.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PatientAccessGrant(Base,UUIDPk,Timestamped):
    __tablename__='patient_access_grants'
    __table_args__=(UniqueConstraint('patient_id','staff_user_id',name='uq_patient_staff_access'),)
    patient_id: Mapped[str] = mapped_column(String(36),ForeignKey('patients.id'),nullable=False,index=True)
    staff_user_id: Mapped[str] = mapped_column(String(36),ForeignKey('staff_users.id'),nullable=False,index=True)
    active: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True)
