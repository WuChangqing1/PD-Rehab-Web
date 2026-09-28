"""Schema bootstrap regression tests.

Guards two problems that only appeared on a fresh deployment:

1. `ensure_schema()` used to call `Base.metadata.create_all`, which builds the
   tables but does not write the alembic_version row. The database then looked
   un-migrated, so the next `alembic upgrade head` failed with
   "table patients already exists". It must migrate instead.

2. `.gitignore` had a bare `models/` rule that matched at any depth and
   silently excluded the source package backend/app/db/models/, so a fresh
   clone could not import the ORM models at all.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_model_modules_are_importable():
    """Catches an ignore rule or packaging mistake hiding the ORM sources."""
    from app.db import models

    for name in (
        "StaffUser",
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
        "AuditLog",
    ):
        assert hasattr(models, name), f"app.db.models is missing {name}"


def test_expected_table_list_is_complete():
    from app.db.models import EXPECTED_TABLES

    assert len(EXPECTED_TABLES) == 13
    assert "training_plans" in EXPECTED_TABLES
    assert "assessment_sessions" in EXPECTED_TABLES
    # V1's "assessments" was replaced by V2's "assessment_sessions"
    assert "assessments" not in EXPECTED_TABLES


def test_orm_metadata_matches_expected_tables():
    from app.db.base import Base
    import app.db.models  # noqa: F401

    from app.db.models import EXPECTED_TABLES

    for table in EXPECTED_TABLES:
        assert table in Base.metadata.tables, f"{table} is not registered on metadata"


def test_alembic_migration_files_exist():
    versions = list((BACKEND_ROOT / "alembic" / "versions").glob("*.py"))
    assert versions, "no alembic revision files found"


def test_alembic_ini_does_not_rely_on_relative_prepend_sys_path():
    """`prepend_sys_path = .` resolves relative to the ini location, which is
    backend/alembic, not backend/. env.py inserts the backend root itself, so an
    active relative entry is misleading and should stay removed."""
    content = (BACKEND_ROOT / "alembic.ini").read_text(encoding="utf-8")
    active = [
        line
        for line in content.splitlines()
        if line.strip().startswith("prepend_sys_path") and not line.strip().startswith("#")
    ]
    assert active == [], f"unexpected active prepend_sys_path: {active}"


def test_ensure_schema_stamps_alembic_version():
    """A database created by ensure_schema must be migration-idempotent.

    Runs in a subprocess because the engine is built at import time, so patching
    DATABASE_URL in-process would have no effect.
    """
    workdir = Path(tempfile.mkdtemp(prefix="pd_schema_"))
    db_path = workdir / "schema_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    script = f"""
import sys
sys.path.insert(0, r"{BACKEND_ROOT}")
from app.db.init_db import ensure_schema
from app.db.session import engine
from sqlalchemy import inspect, text

created = ensure_schema()
insp = inspect(engine)
domain = [t for t in insp.get_table_names() if not t.startswith("sqlite_")]
with engine.connect() as c:
    stamped = c.execute(text("select version_num from alembic_version")).scalar()
print("CREATED", created)
print("DOMAIN", len(domain))
print("STAMPED", stamped)
"""
    full_env = {
        **os.environ,
        "DATABASE_URL": db_url,
        "PYTHONPATH": str(BACKEND_ROOT),
    }
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(BACKEND_ROOT),
            timeout=180,
        )
        assert result.returncode == 0, result.stderr
        assert "CREATED True" in result.stdout
        # 13 domain tables + alembic_version. Seeing alembic_version present in
        # this count is itself part of the guarantee being tested.
        assert "DOMAIN 14" in result.stdout, result.stdout
        assert "STAMPED 69a1df545cdc" in result.stdout, result.stdout

        # And the follow-up upgrade must be a clean no-op.
        upgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(BACKEND_ROOT),
            timeout=180,
        )
        assert upgrade.returncode == 0, upgrade.stderr
        assert "already exists" not in (upgrade.stderr + upgrade.stdout)

        check_engine = create_engine(db_url)
        assert "patients" in inspect(check_engine).get_table_names()
        check_engine.dispose()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
