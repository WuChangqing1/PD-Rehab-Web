"""Database session and engine setup.

Development uses SQLite. MySQL stays switchable purely through DATABASE_URL,
e.g. mysql+pymysql://user:pass@host:3306/pd_rehab?charset=utf8mb4
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import PROJECT_ROOT, settings


def _normalise_sqlite_url(url: str) -> tuple[str, dict]:
    """Make relative sqlite paths absolute against the project root."""
    connect_args: dict = {}
    if url.startswith("sqlite"):
        prefix, _, raw = url.partition(":///")
        db_path = raw
        if db_path and db_path != ":memory:":
            p = Path(db_path)
            if not p.is_absolute():
                p = (PROJECT_ROOT / db_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            url = f"{prefix}:///{p.as_posix()}"
        # FastAPI runs handlers in a threadpool; allow cross-thread use.
        connect_args = {"check_same_thread": False}
    return url, connect_args


DATABASE_URL, _CONNECT_ARGS = _normalise_sqlite_url(settings.database_url)

engine = create_engine(
    DATABASE_URL,
    echo=settings.db_echo,
    future=True,
    pool_pre_ping=True,
    connect_args=_CONNECT_ARGS,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enable FK enforcement and WAL on SQLite (no-op for MySQL)."""
    module = type(dbapi_connection).__module__
    if "sqlite" not in module:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
