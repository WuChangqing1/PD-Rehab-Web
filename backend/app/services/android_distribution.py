"""Fail-closed public catalog for independently verified, approved APKs."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

PACKAGE = "com.pianoforparkinson.piano_practice"


class ApprovedRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approved: bool
    channel: str
    filename: str
    version_name: str = Field(min_length=1, max_length=50)
    version_code: int = Field(gt=0)
    package_id: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    signer_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    min_sdk: int = Field(ge=21)
    published_at: str
    shorebird_app_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    shorebird_release: str = Field(min_length=1, max_length=80)


def _tool(name: str, args: list[str]) -> str:
    executable = os.environ.get(name, "")
    if not executable or not Path(executable).is_file():
        raise ValueError("APK verification tool unavailable")
    return subprocess.run([executable, *args], check=True, capture_output=True,
                          text=True, timeout=60).stdout


def verified_release() -> tuple[ApprovedRelease, Path] | None:
    """Never expose filesystem paths or validation failure details publicly.

    The release directory is administrator-managed and must be immutable to the
    app worker. The configured certificate is the independently approved trust
    anchor, never taken from the manifest itself.
    """
    try:
        trust = settings.android_expected_signer_sha256.lower().replace(":", "")
        if not re.fullmatch(r"[a-f0-9]{64}", trust):
            return None
        directory = settings._resolve(settings.android_release_dir)
        release = ApprovedRelease.model_validate_json((directory / "stable.json").read_bytes())
        if not release.approved or release.channel != "stable" or release.package_id != PACKAGE:
            return None
        if release.shorebird_release != f"{release.version_name}+{release.version_code}":
            return None
        if release.signer_sha256 != trust:
            return None
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.apk", release.filename):
            return None
        published = datetime.fromisoformat(release.published_at.replace("Z", "+00:00"))
        if published.tzinfo is None:
            return None
        apk = directory / release.filename
        if apk.is_symlink() or not apk.is_file() or apk.stat().st_size != release.size_bytes:
            return None
        with apk.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != release.sha256:
            return None
        certs = _tool("ANDROID_APKSIGNER", ["verify", "--verbose", "--print-certs", str(apk)])
        fingerprints = re.findall(r"certificate SHA-256 digest: ([a-fA-F0-9]+)", certs)
        if not fingerprints or any(value.lower() != trust for value in fingerprints):
            return None
        if re.search(r"certificate DN:.*(?:Android Debug|CN=debug)", certs, re.I):
            return None
        badging = _tool("ANDROID_AAPT", ["dump", "badging", str(apk)])
        package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
        sdk = re.search(r"sdkVersion:'(\d+)'", badging)
        if not package or package.groups() != (PACKAGE, str(release.version_code), release.version_name):
            return None
        if not sdk or int(sdk[1]) != release.min_sdk or "application-debuggable" in badging:
            return None
        # A plain Flutter APK must never be advertised as a Shorebird base.
        with zipfile.ZipFile(apk) as archive:
            config = archive.read("assets/flutter_assets/shorebird.yaml").decode("utf-8")
        app_id = re.search(r"(?m)^app_id:\s*[\"']?([a-f0-9-]{36})", config)
        if not app_id or app_id[1] != release.shorebird_app_id:
            return None
        return release, apk
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError):
        return None
