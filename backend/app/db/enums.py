"""Domain enumerations.

Stored as plain strings for SQLite/MySQL portability, constrained by constants
and (where useful) CHECK constraints in the migrations.
"""

from __future__ import annotations

from enum import StrEnum


class StaffRole(StrEnum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"


class Sex(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class Hand(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class DominantHand(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    AMBIDEXTROUS = "AMBIDEXTROUS"
    UNKNOWN = "UNKNOWN"


class AffectedSide(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BILATERAL = "BILATERAL"
    UNKNOWN = "UNKNOWN"


class MedicationState(StrEnum):
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"


class AssessmentSessionType(StrEnum):
    COMPREHENSIVE = "COMPREHENSIVE"
    MICRO_EXPRESSION_ONLY = "MICRO_EXPRESSION_ONLY"
    FINGER_TAPPING_ONLY = "FINGER_TAPPING_ONLY"
    FUNCTIONAL_TEST = "FUNCTIONAL_TEST"


class SessionStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class MediaType(StrEnum):
    MICRO_EXPRESSION_VIDEO = "MICRO_EXPRESSION_VIDEO"
    FINGER_TAPPING_VIDEO = "FINGER_TAPPING_VIDEO"
    POSE_VIDEO = "POSE_VIDEO"
    REPORT = "REPORT"


class BaselineType(StrEnum):
    COMPREHENSIVE = "COMPREHENSIVE"
    FINGER_TAPPING = "FINGER_TAPPING"
    PIANO_CALIBRATION = "PIANO_CALIBRATION"
    POSE = "POSE"


class TrainingPlanStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PianoMode(StrEnum):
    """The four training modes required by spec V2 section 15."""

    SINGLE_KEY_RHYTHM = "SINGLE_KEY_RHYTHM"
    ALTERNATING_HANDS = "ALTERNATING_HANDS"
    MAPPED_SEQUENCE = "MAPPED_SEQUENCE"
    FOLLOW_THE_BEAT = "FOLLOW_THE_BEAT"
    CALIBRATION = "CALIBRATION"


class HandMode(StrEnum):
    SINGLE = "SINGLE"
    ALTERNATING = "ALTERNATING"
    BOTH = "BOTH"


class FingerHint(StrEnum):
    THUMB = "THUMB"
    INDEX = "INDEX"
    MIDDLE = "MIDDLE"
    RING = "RING"
    LITTLE = "LITTLE"


WEAK_FINGERS = (FingerHint.RING, FingerHint.LITTLE)


class PoseExerciseType(StrEnum):
    """The five first-version exercises (spec V2 section 27)."""

    MOUNTAIN_ARMS_UP = "MOUNTAIN_ARMS_UP"
    ARMS_LATERAL_RAISE = "ARMS_LATERAL_RAISE"
    SIDE_BEND_STRETCH = "SIDE_BEND_STRETCH"
    SEATED_TRUNK_ROTATION = "SEATED_TRUNK_ROTATION"
    SEATED_ALTERNATING_ARM_RAISE = "SEATED_ALTERNATING_ARM_RAISE"


class FunctionalTestType(StrEnum):
    NINE_HOLE_PEG = "NINE_HOLE_PEG"
    BOX_AND_BLOCK = "BOX_AND_BLOCK"
    HAND_COORDINATION = "HAND_COORDINATION"
    MDS_UPDRS = "MDS_UPDRS"
    PDQ39 = "PDQ39"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class JobType(StrEnum):
    MICRO_EXPRESSION_ANALYSIS = "MICRO_EXPRESSION_ANALYSIS"
    FINGER_TAPPING_ANALYSIS = "FINGER_TAPPING_ANALYSIS"
    POSE_ANALYSIS = "POSE_ANALYSIS"
    REPORT_EXPORT = "REPORT_EXPORT"
