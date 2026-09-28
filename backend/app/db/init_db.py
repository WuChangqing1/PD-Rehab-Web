"""Application bootstrap: ensures the schema exists and the first admin user."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import StaffUser
from app.db.session import SessionLocal, engine

logger = get_logger(__name__)

# backend/  (this file is backend/app/db/init_db.py)
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _table_names() -> list[str]:
    return inspect(engine).get_table_names()


def ensure_schema(allow_create_all: bool = True) -> bool:
    """Bring the database schema up to date.

    Migrations are the single source of truth. Running them here (instead of
    Base.metadata.create_all) matters because create_all builds the tables
    *without* writing the alembic_version row, which leaves the database looking
    un-migrated. A later `alembic upgrade head` then tries to create tables that
    already exist and fails with "table ... already exists".

    Strategy:
      1. If the database is empty, run `alembic upgrade head`.
      2. If alembic is missing, has no revisions, or fails for any reason, fall
         back to create_all so the app still starts -- but say so loudly.
    """
    existing = _table_names()
    if "staff_users" in existing:
        return False

    if allow_create_all:
        try:
            command.upgrade(_alembic_config(), "head")
            logger.info(
                "schema created via alembic upgrade head (%d tables)",
                len([t for t in _table_names() if not t.startswith("sqlite_")]),
            )
            return True
        except Exception as exc:  # noqa: BLE001 - startup must not depend on this
            logger.warning(
                "alembic upgrade failed (%s: %s); falling back to create_all",
                type(exc).__name__,
                exc,
            )

    from app.db.base import Base
    import app.db.models  # noqa: F401  (register tables)

    logger.warning(
        "creating schema with Base.metadata.create_all; alembic_version will NOT "
        "be stamped, so run 'alembic stamp head' before any future migration"
    )
    Base.metadata.create_all(bind=engine)
    logger.info(
        "created %d tables: %s",
        len(Base.metadata.tables),
        ", ".join(sorted(Base.metadata.tables)),
    )
    return True


def ensure_bootstrap_admin() -> bool:
    """Create the first ADMIN account if no staff user exists yet."""
    with SessionLocal() as db:
        existing = db.execute(select(StaffUser.id).limit(1)).first()
        if existing is not None:
            return False

        if settings.bootstrap_admin_password == "CHANGE_ME_admin":
            logger.warning(
                "creating bootstrap admin with the default password; "
                "set BOOTSTRAP_ADMIN_PASSWORD in .env before any real use"
            )

        admin = StaffUser(
            username=settings.bootstrap_admin_username,
            password_hash=hash_password(settings.bootstrap_admin_password),
            display_name=settings.bootstrap_admin_display_name,
            role="ADMIN",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info("bootstrap admin '%s' created", admin.username)
        return True
