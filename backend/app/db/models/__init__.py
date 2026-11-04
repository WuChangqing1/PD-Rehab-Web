"""ORM model package.

Importing this package registers every table on Base.metadata, which is what
Alembic autogenerate relies on.
"""

from app.db.models.face_recording import FaceRecording
from app.db.base import Base
from app.db.models.assessment import (
    AssessmentSession,
    FingerTappingResult,
    FunctionalAssessment,
    MediaFile,
    MicroExpressionResult,
)
from app.db.models.baseline import Baseline
from app.db.models.guided_song import GuidedSongSession
from app.db.models.patient import Patient
from app.db.models.patient_number import PatientNumberAllocation
from app.db.models.staff import AuditLog, StaffUser
from app.db.models.integration import PatientAccessGrant, DevicePatientLink, ExternalPracticeRecord, MobileFaceJob, ExpertChatTurn
from app.db.models.training import PianoEvent, PianoSession, PoseSession, TrainingPlan

__all__ = [
    "Base",
    "StaffUser",
    "AuditLog",
    "Patient",
    "PatientNumberAllocation",
    "AssessmentSession",
    "MediaFile",
    "MicroExpressionResult",
    "FingerTappingResult",
    "FunctionalAssessment",
    "Baseline",
    "DevicePatientLink", "ExternalPracticeRecord", "MobileFaceJob", "ExpertChatTurn",
    "TrainingPlan",
    "PianoSession",
    "PianoEvent",
    "PoseSession",
]

# The original 13 domain tables plus isolated guided-song sessions.
EXPECTED_TABLES = [
    "face_recordings",
    "staff_users",
    "patients",
    "patient_number_allocations",
    "assessment_sessions",
    "media_files",
    "micro_expression_results",
    "finger_tapping_results",
    "baselines",
    "training_plans",
    "piano_sessions",
    "piano_events",
    "pose_sessions",
    "functional_assessments",
    "audit_logs",
    "guided_song_sessions",
    "patient_access_grants", "device_patient_links", "external_practice_records", "mobile_face_jobs", "expert_chat_turns",
]
