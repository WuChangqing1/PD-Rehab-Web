"""Application bootstrap: ensures the schema exists and the first admin user."""

from __future__ import annotations

from sqlalchemy import inspect, select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import StaffUser
from app.db.session import SessionLocal, engine

logger = get_logger(__name__)


def ensure_schema() -> bool:
    """Create tables if the database is empty.

    Alembic remains the source of truth; this only prevents a blank database
    from breaking first run. It never modifies an existing schema.
    """
    from app.db.base import Base
    import app.db.models  # noqa: F401  (register tables)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    if "staff_users" in existing:
        return False

    logger.info("database is empty; creating schema from metadata")
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
