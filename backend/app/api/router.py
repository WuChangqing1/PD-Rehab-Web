"""Router aggregation. Mounted under /api by main.py."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import integration, active_training, assessment_sessions, auth, followup, guided_song, jobs, live_emotion, patients, piano, pose, system

from app.api import face_recordings, integration_changes
from app.api import mobile_auth
from app.api import mobile_external_auth

api_router = APIRouter()
api_router.include_router(mobile_auth.router)
api_router.include_router(mobile_external_auth.router)
api_router.include_router(face_recordings.router)
api_router.include_router(active_training.router)
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(followup.router)
api_router.include_router(assessment_sessions.router)
api_router.include_router(piano.router)
api_router.include_router(pose.router)
api_router.include_router(system.router)
api_router.include_router(jobs.router)
api_router.include_router(guided_song.router)

api_router.include_router(live_emotion.router)
api_router.include_router(integration.router)
api_router.include_router(integration_changes.router)

__all__ = ["api_router"]

from app.api import staff_accounts
api_router.include_router(staff_accounts.router)

from app.api import documents, business_exports, patient_reports, android_distribution
api_router.include_router(documents.router)
api_router.include_router(business_exports.router)
api_router.include_router(patient_reports.router)
api_router.include_router(android_distribution.router)
