import hashlib
import json
import zipfile
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.services import android_distribution as service
from app.api.android_distribution import router

CERT = "a" * 64
APP_ID = "12345678-1234-1234-1234-123456789abc"

@pytest.fixture
def approved(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, "android_release_dir", str(tmp_path))
    monkeypatch.setattr(service.settings, "android_expected_signer_sha256", CERT)
    apk = tmp_path / "qinban-0.1.74.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("assets/flutter_assets/shorebird.yaml", f"app_id: {APP_ID}\nauto_update: false\n")
    manifest = dict(approved=True, channel="stable", filename=apk.name,
        version_name="0.1.74", version_code=75, package_id=service.PACKAGE,
        size_bytes=apk.stat().st_size, sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
        signer_sha256=CERT, min_sdk=24, published_at="2026-11-19T12:00:00Z",
        shorebird_app_id=APP_ID, shorebird_release="0.1.74+75")
    def save(): (tmp_path / "stable.json").write_text(json.dumps(manifest))
    save()
    def tool(name, args):
        if name == "ANDROID_APKSIGNER":
            return f"Signer #1 certificate DN: CN=Approved\nSigner #1 certificate SHA-256 digest: {CERT}"
        return f"package: name='{service.PACKAGE}' versionCode='75' versionName='0.1.74'\nsdkVersion:'24'"
    monkeypatch.setattr(service, "_tool", tool)
    return manifest, apk, save


def test_public_api_disables_download_without_trust(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, "android_release_dir", str(tmp_path))
    monkeypatch.setattr(service.settings, "android_expected_signer_sha256", "")
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/android/latest")
        assert response.json()["available"] is False
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/android/download").status_code == 404


def test_approved_metadata_and_anonymous_download(approved):
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        result = client.get("/android/latest").json()
        assert result["available"] and result["sha256"] == approved[0]["sha256"]
        assert "filename" not in result and "approved" not in result
        response = client.get("/android/download", headers={"Range": "bytes=0-9"})
        assert response.status_code == 206
        assert len(response.content) == 10
        assert response.headers["content-type"] == "application/vnd.android.package-archive"


@pytest.mark.parametrize("field,value", [("filename", "../secret.apk"), ("filename", "/tmp/app.apk"),
    ("approved", False), ("channel", "staging"), ("signer_sha256", "b"*64),
    ("package_id", "other.app"), ("sha256", "b"*64), ("size_bytes", 1),
    ("published_at", "yesterday"), ("published_at", "2026-11-19"),
    ("shorebird_app_id", "22345678-1234-1234-1234-123456789abc")])
def test_rejects_unapproved_mismatched_or_unsafe_manifest(approved, field, value):
    manifest, _, save = approved
    manifest[field] = value; save()
    assert service.verified_release() is None


def test_rejects_debug_certificate(approved, monkeypatch):
    monkeypatch.setattr(service, "_tool", lambda *args: f"Signer #1 certificate DN: C=US, O=Android, CN=Android Debug\nSigner #1 certificate SHA-256 digest: {CERT}")
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


def test_plain_flutter_apk_is_not_a_shorebird_base(approved):
    manifest, apk, save = approved
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("assets/flutter_assets/example.txt", "ordinary build")
    manifest["size_bytes"] = apk.stat().st_size
    manifest["sha256"] = hashlib.sha256(apk.read_bytes()).hexdigest()
    save()
    assert service.verified_release() is None


def test_release_identifier_must_match_version(approved):
    manifest, _, save = approved
    manifest["shorebird_release"] = "0.0.1+1"
    save()
    assert service.verified_release() is None
