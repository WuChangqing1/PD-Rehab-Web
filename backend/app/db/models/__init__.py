"""ORM model package.

Importing this package registers every table on Base.metadata, which is what
Alembic autogenerate relies on.
"""

from app.db.base import Base
from app.db.models.assessment import (
    AssessmentSession,
    FingerTappingResult,
    FunctionalAssessment,
    MediaFile,
    MicroExpressionResult,
)
from app.db.models.baseline import Baseline
from app.db.models.patient import Patient
from app.db.models.staff import AuditLog, StaffUser
from app.db.models.training import PianoEvent, PianoSession, PoseSession, TrainingPlan

__all__ = [
    "Base",
    "StaffUser",
    "AuditLog",
    "Patient",
    "AssessmentSession",
    "MediaFile",
    "MicroExpressionResult",
    "FingerTappingResult",
    "FunctionalAssessment",
    "Baseline",
    "TrainingPlan",
    "PianoSession",
    "PianoEvent",
    "PoseSession",
]

# The 13 tables required by the task brief.
EXPECTED_TABLES = [
    "staff_users",
    "patients",
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
]
