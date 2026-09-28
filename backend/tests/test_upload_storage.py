"""Upload storage tests.

Regression guard: `store_upload` used to derive the stored path with a bare
`target.relative_to(PROJECT_ROOT)`. That works locally, where UPLOAD_DIR sits
inside the project, but on a server the upload directory is deliberately
outside the code tree. There it raised ValueError and surfaced as an opaque
HTTP 500 for every upload, which is how the first production deployment failed.

Note on temporary directories: pytest's `tmp_path` is unusable on this machine
because its base directory under %TEMP% denies access. The `scratch_dir` fixture
below creates a directory inside the project (git-ignored data/tmp/) instead.
"""

from __future__ import annotations

import importlib
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import PROJECT_ROOT
from app.core.errors import APIError
from app.db.enums import MediaType

_SCRATCH_ROOT = PROJECT_ROOT / "data" / "tmp"
# Deliberately outside PROJECT_ROOT, to exercise the production layout where
# UPLOAD_DIR sits outside the code tree.
_SCRATCH_OUTSIDE = PROJECT_ROOT.parent / "_pd_pytest_scratch"


@pytest.fixture
def scratch_inside() -> Iterator[Path]:
    """A scratch directory *inside* the project (local development layout)."""
    path = _SCRATCH_ROOT / f"test-{uuid.uuid4().hex[:12]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def scratch_outside() -> Iterator[Path]:
    """A scratch directory *outside* the project (server layout)."""
    path = _SCRATCH_OUTSIDE / f"test-{uuid.uuid4().hex[:12]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        # remove the parent too when nothing else is left in it
        try:
            _SCRATCH_OUTSIDE.rmdir()
        except OSError:
            pass


@pytest.fixture
def scratch_dir(scratch_inside: Path) -> Path:
    """Default scratch directory for tests that do not care about layout."""
    return scratch_inside


def _reload_with_upload_dir(monkeypatch, upload_dir: Path, max_mb: str | None = None):
    """Point UPLOAD_DIR at `upload_dir` and reload the module that reads it."""
    import app.core.config as config_module

    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    if max_mb is not None:
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", max_mb)
    monkeypatch.setattr(config_module, "settings", config_module.Settings(), raising=True)

    import app.services.assessment_service as svc

    importlib.reload(svc)
    return svc


def test_upload_outside_project_root_stores_absolute_path(scratch_outside, monkeypatch):
    """The production layout: UPLOAD_DIR is not under PROJECT_ROOT."""
    outside = scratch_outside / "uploads"
    assert not str(outside).startswith(str(PROJECT_ROOT))
    svc = _reload_with_upload_dir(monkeypatch, outside)
    try:
        path, digest, stored = svc.store_upload(
            patient_id="patient-1",
            original_filename="capture.mp4",
            content=b"fake video bytes",
            media_type=MediaType.FINGER_TAPPING_VIDEO,
        )
        # No ValueError; an absolute path outside the project is returned.
        assert Path(stored).is_absolute(), stored
        assert not str(path).startswith(str(PROJECT_ROOT))
        assert path.is_file()
        assert len(digest) == 64
    finally:
        importlib.reload(svc)


def test_upload_inside_project_root_stores_relative_path(scratch_inside, monkeypatch):
    """The local layout: a relative, portable path is preferred."""
    inside = scratch_inside / "uploads"
    svc = _reload_with_upload_dir(monkeypatch, inside)
    try:
        _path, _digest, stored = svc.store_upload(
            patient_id="patient-1",
            original_filename="capture.mp4",
            content=b"fake video bytes",
            media_type=MediaType.FINGER_TAPPING_VIDEO,
        )
        assert not Path(stored).is_absolute(), stored
        assert stored.startswith("data/"), stored
    finally:
        importlib.reload(svc)


def test_upload_filename_never_contains_patient_name(scratch_dir, monkeypatch):
    """Spec V2 section 51: uploaded files must use UUID names."""
    svc = _reload_with_upload_dir(monkeypatch, scratch_dir / "uploads")
    try:
        path, _digest, _stored = svc.store_upload(
            patient_id="patient-1",
            original_filename="张三_帕金森.mp4",
            content=b"bytes",
            media_type=MediaType.FINGER_TAPPING_VIDEO,
        )
        assert "张三" not in path.name
        assert path.suffix == ".mp4"
        # uuid4 form: 36 characters (8-4-4-4-12)
        assert len(path.stem) == 36
        assert path.stem.count("-") == 4
    finally:
        importlib.reload(svc)


def test_upload_path_grouped_by_patient_and_date(scratch_dir, monkeypatch):
    from datetime import date

    svc = _reload_with_upload_dir(monkeypatch, scratch_dir / "uploads")
    try:
        path, _digest, _stored = svc.store_upload(
            patient_id="patient-abc",
            original_filename="capture.mp4",
            content=b"bytes",
            media_type=MediaType.FINGER_TAPPING_VIDEO,
        )
        assert "patient-abc" in path.parts
        assert date.today().isoformat() in path.parts
    finally:
        importlib.reload(svc)


def test_unsupported_extension_rejected(scratch_dir, monkeypatch):
    svc = _reload_with_upload_dir(monkeypatch, scratch_dir / "uploads")
    try:
        with pytest.raises(APIError) as exc:
            svc.store_upload(
                patient_id="p1",
                original_filename="notes.txt",
                content=b"hello",
                media_type=MediaType.FINGER_TAPPING_VIDEO,
            )
        assert exc.value.status_code == 415
        assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"
    finally:
        importlib.reload(svc)


def test_upload_larger_than_limit_rejected(scratch_dir, monkeypatch):
    svc = _reload_with_upload_dir(monkeypatch, scratch_dir / "uploads", max_mb="1")
    try:
        with pytest.raises(APIError) as exc:
            svc.store_upload(
                patient_id="p1",
                original_filename="big.mp4",
                content=b"x" * (2 * 1024 * 1024),
                media_type=MediaType.FINGER_TAPPING_VIDEO,
            )
        assert exc.value.status_code == 413
        assert exc.value.code == "FILE_TOO_LARGE"
    finally:
        importlib.reload(svc)


def test_report_media_type_skips_extension_check(scratch_dir, monkeypatch):
    """Reports may be non-video; only videos are extension-restricted."""
    svc = _reload_with_upload_dir(monkeypatch, scratch_dir / "uploads")
    try:
        path, _digest, _stored = svc.store_upload(
            patient_id="p1",
            original_filename="report.pdf",
            content=b"%PDF-1.4",
            media_type=MediaType.REPORT,
        )
        assert path.is_file()
        assert path.suffix == ".pdf"
    finally:
        importlib.reload(svc)
