"""Network retries use separate real SQLite transactions, not one shared connection."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from tempfile import TemporaryDirectory
import time

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event, func, select

from app.db.base import Base
from app.db.models import PianoEvent, PianoSession
from tests.test_piano_api import _patient
from tests.test_piano_extended_recipes import event


@pytest.fixture
def engine():
    # Avoid pytest's shared temp root, which can be owned by another Windows
    # execution account; this directory belongs exclusively to this test.
    with TemporaryDirectory(prefix="pd-piano-concurrent-") as directory:
        engine = create_engine(f"sqlite:///{(Path(directory) / 'retry.sqlite3').as_posix()}",
                               connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()


def concurrent_posts(client, path, payload, headers, engine, table):
    barrier = Barrier(2)

    def slow_deduplication_read(connection, cursor, statement, parameters, context, executemany):
        # Widen the real read/write race without mocking application behavior.
        # With serialization, the second transaction waits before this read.
        if statement.lstrip().upper().startswith("SELECT") and f"FROM {table}" in statement:
            time.sleep(0.05)

    sqlalchemy_event.listen(engine, "after_cursor_execute", slow_deduplication_read)
    try:
        def post():
            barrier.wait(timeout=5)
            return client.post(path, json=payload, headers=headers)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(post), pool.submit(post)]
            return [future.result(timeout=15) for future in futures]
    finally:
        sqlalchemy_event.remove(engine, "after_cursor_execute", slow_deduplication_read)


def test_concurrent_create_retry_writes_one_session(app_client, auth_headers, engine, db):
    patient = _patient(app_client, auth_headers)
    responses = concurrent_posts(app_client, f"/api/patients/{patient['id']}/piano/sessions",
        {"mode": "SINGLE_KEY_RHYTHM", "client_request_id": "same-network-request"},
        auth_headers, engine, "piano_sessions")
    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert db.scalar(select(func.count()).select_from(PianoSession)) == 1


def test_concurrent_event_retry_writes_one_raw_event(app_client, auth_headers, engine, db):
    patient = _patient(app_client, auth_headers)
    session = app_client.post(f"/api/patients/{patient['id']}/piano/sessions",
        json={"mode": "SINGLE_KEY_RHYTHM"}, headers=auth_headers).json()
    responses = concurrent_posts(app_client, f"/api/piano/sessions/{session['id']}/events/batch",
        {"events": [event(0, None, actual=500)]}, auth_headers, engine, "piano_events")
    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["stored"] for response in responses) == [0, 1]
    assert db.scalar(select(func.count()).select_from(PianoEvent)) == 1
