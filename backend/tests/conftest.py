"""Shared pytest fixtures.

Every test runs against a fresh in-memory SQLite database, so nothing touches
the development database and tests cannot leak state into each other.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Keep the app's own startup from touching the real data directory during tests.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "test-admin-password")

from app.db.base import Base  # noqa: E402
from app.db.models import StaffUser  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402

TEST_ADMIN = {
    "username": "testdoctor",
    "password": "test-password-123",
    "display_name": "测试医生",
    "role": "DOCTOR",
}


@pytest.fixture(scope="function")
def engine():
    """Dedicated in-memory database per test."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    import app.db.models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture(scope="function")
def db(engine) -> Generator[Session, None, None]:
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = maker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def app_client(engine, db) -> Generator[TestClient, None, None]:
    """TestClient bound to the per-test database."""
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        session = maker()
        try:
            yield session
        finally:
            session.close()

    from app.main import app
    from app.ml.bootstrap import load_all_models

    app.dependency_overrides[get_db] = override_get_db
    load_all_models()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def staff_user(db: Session) -> StaffUser:
    user = StaffUser(
        username=TEST_ADMIN["username"],
        password_hash=hash_password(TEST_ADMIN["password"]),
        display_name=TEST_ADMIN["display_name"],
        role=TEST_ADMIN["role"],
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_headers(app_client: TestClient, staff_user: StaffUser) -> dict[str, str]:
    response = app_client.post(
        "/api/auth/login",
        json={
            "username": TEST_ADMIN["username"],
            "password": TEST_ADMIN["password"],
        },
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def patient_payload() -> dict:
    return {
        "hospital_number": "P0001",
        "name": "张三（虚拟）",
        "sex": "MALE",
        "birthday": "1955-03-12",
        "phone": "13800000000",
        "dominant_hand": "RIGHT",
        "affected_side": "LEFT",
        "diagnosis_date": "2019-06-01",
        "disease_duration_years": 7.0,
        "medication_state": "ON",
        "current_medications": "左旋多巴",
        "medical_history": "高血压",
    }
