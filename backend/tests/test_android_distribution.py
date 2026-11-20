import hashlib
import importlib.util
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.services import android_distribution as service
from app.api.android_distribution import router

CERT = "a" * 64

@pytest.fixture
def approved(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, "android_release_dir", str(tmp_path))
    monkeypatch.setattr(service.settings, "android_expected_signer_sha256", CERT)
    apk = tmp_path / "0.1.74" / "qinban-0.1.74-android-universal.apk"
    apk.parent.mkdir()
    apk.write_bytes(b"Unit test full APK artifact; verification tools are mocked")
    manifest = dict(schemaVersion=1, packageName=service.PACKAGE,
        versionName="0.1.74", versionCode=75, apkUrl=service.PUBLIC_PREFIX+"0.1.74/"+apk.name,
        sizeBytes=apk.stat().st_size, sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
        notesZh="更新内容", notesEn="Release notes")
    def save(): (tmp_path / service.MANIFEST_NAME).write_text(json.dumps(manifest))
    save()
    def tool(name, args):
        if name == "ANDROID_APKSIGNER":
            return f"Signer #1 certificate DN: CN=Approved\nSigner #1 certificate SHA-256 digest: {CERT}"
        return f"package: name='{service.PACKAGE}' versionCode='75' versionName='0.1.74'\nsdkVersion:'24'"
    monkeypatch.setattr(service, "_tool", tool)
    return manifest, apk, save


def test_public_api_disables_download_without_trust(approved, monkeypatch):
    monkeypatch.setattr(service.settings, "android_expected_signer_sha256", "")
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/android/latest")
        assert response.json()["available"] is False
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/android/download").status_code == 404


def test_same_manifest_authority_serves_ordinary_verified_apk(approved):
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        result = client.get("/android/latest").json()
        assert result["available"]
        for key, value in approved[0].items(): assert result[key] == value
        assert result["download_url"] == approved[0]["apkUrl"]
        assert not any("shorebird" in key for key in result)
        response = client.get("/android/download", headers={"Range": "bytes=0-9"})
        assert response.status_code == 206 and len(response.content) == 10
        assert response.headers["content-type"] == "application/vnd.android.package-archive"


@pytest.mark.parametrize("field,value", [("schemaVersion", 2), ("schemaVersion", True),
    ("packageName", "other.app"), ("sha256", "b"*64), ("sizeBytes", 1),
    ("versionCode", 74), ("versionName", "0.1.73"),
    ("apkUrl", service.PUBLIC_PREFIX+"../secret.apk"),
    ("apkUrl", "https://other.example/app.apk"),
    ("apkUrl", service.PUBLIC_PREFIX+"%2e%2e/secret.apk"),
    ("apkUrl", service.PUBLIC_PREFIX+"app.apk?redirect=x"),
    ("apkUrl", "http://ccqspace.site/pd-rehab/assets/app-releases/app.apk"),
    ("notesZh", "x"*2001)])
def test_rejects_incompatible_or_unsafe_manifest(approved, field, value):
    manifest, _, save = approved
    manifest[field] = value; save()
    assert service.verified_release() is None


def test_rejects_debug_certificate(approved, monkeypatch):
    monkeypatch.setattr(service, "_tool", lambda *args: f"Signer #1 certificate DN: CN=Android Debug\nSigner #1 certificate SHA-256 digest: {CERT}")
    assert service.verified_release() is None


def test_rejects_wrong_certificate(approved, monkeypatch):
    monkeypatch.setattr(service, "_tool", lambda *args: f"Signer #1 certificate SHA-256 digest: {'b'*64}")
    assert service.verified_release() is None


def test_rejects_debuggable_apk(approved, monkeypatch):
    original = service._tool
    monkeypatch.setattr(service, "_tool", lambda name,args: original(name,args)+"\napplication-debuggable")
    assert service.verified_release() is None


def test_verification_tools_fail_closed(approved, monkeypatch):
    def fail(*args): raise ValueError("tool unavailable")
    monkeypatch.setattr(service, "_tool", fail)
    assert service.verified_release() is None


def test_tampered_apk_is_not_served(approved):
    approved[1].write_bytes(b"tampered")
    assert service.verified_release() is None


def preparer():
    path = Path(__file__).resolve().parents[2] / "scripts" / "prepare_android_release.py"
    spec = importlib.util.spec_from_file_location("prepare_android_release", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_preparation_generates_teammate_schema_and_verified_bytes(approved, tmp_path):
    output = tmp_path / "review-bundle"
    result = preparer().prepare_release(approved[1], output, trusted_signer=CERT,
        notes_zh="更新", notes_en="Update", approved=True)
    assert result["schemaVersion"] == 1 and result["versionCode"] == 75
    assert set(result) == set(approved[0])
    assert (output / service.MANIFEST_NAME).is_file()
    target = output / service.apk_relative_path(result["apkUrl"])
    assert target.read_bytes() == approved[1].read_bytes()
    with pytest.raises(ValueError, match="versionCode must increase"):
        preparer().prepare_release(approved[1], output, trusted_signer=CERT,
            notes_zh="更新", notes_en="Update", approved=True)


def test_preparation_requires_explicit_artifact_approval(approved, tmp_path):
    output = tmp_path / "not-approved"
    with pytest.raises(ValueError, match="approval"):
        preparer().prepare_release(approved[1], output, trusted_signer=CERT,
            notes_zh="更新", notes_en="Update", approved=False)
    assert not output.exists()



def test_verification_cache_avoids_rehashing_and_tools(approved, monkeypatch):
    original_digest = service.hashlib.file_digest
    original_inspect = service.inspect_apk
    calls = {"hash": 0, "inspect": 0}
    def digest(*args):
        calls["hash"] += 1
        return original_digest(*args)
    def inspect(*args):
        calls["inspect"] += 1
        return original_inspect(*args)
    monkeypatch.setattr(service.hashlib, "file_digest", digest)
    monkeypatch.setattr(service, "inspect_apk", inspect)
    assert service.verified_release() is not None
    assert service.verified_release() is not None
    assert calls == {"hash": 1, "inspect": 1}


def test_changed_manifest_revalidates_cache(approved, monkeypatch):
    assert service.verified_release() is not None
    manifest, _, save = approved
    manifest["notesZh"] = "New reviewed release notes"
    save()
    def fail(*args): raise ValueError("changed verifier rejected artifact")
    monkeypatch.setattr(service, "inspect_apk", fail)
    assert service.verified_release() is None


def test_changed_apk_does_not_reuse_success(approved):
    assert service.verified_release() is not None
    original = approved[1].read_bytes()
    approved[1].write_bytes(b"X" + original[1:])
    assert service.verified_release() is None


def test_changed_signer_does_not_reuse_success(approved, monkeypatch):
    assert service.verified_release() is not None
    monkeypatch.setattr(service.settings, "android_expected_signer_sha256", "b" * 64)
    assert service.verified_release() is None


def test_artifact_changed_during_verification_is_rejected(approved, monkeypatch):
    original = service.inspect_apk
    def inspect(*args):
        facts = original(*args)
        approved[1].write_bytes(b"changed during verification")
        return facts
    monkeypatch.setattr(service, "inspect_apk", inspect)
    assert service.verified_release() is None



def test_busy_verification_fails_closed_without_waiting(approved):
    service._verification_lock.acquire()
    try:
        assert service.verified_release() is None
    finally:
        service._verification_lock.release()
