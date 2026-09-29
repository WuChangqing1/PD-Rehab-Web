"""Router aggregation. Mounted under /api by main.py."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import assessment_sessions, auth, jobs, patients, piano, system

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(assessment_sessions.router)
api_router.include_router(piano.router)
api_router.include_router(system.router)
api_router.include_router(jobs.router)

__all__ = ["api_router"]
