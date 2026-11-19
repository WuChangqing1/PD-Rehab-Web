"""Verify the same full-APK manifest consumed by the teammate Android updater."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from app.core.config import settings

PACKAGE = "com.pianoforparkinson.piano_practice"
PUBLIC_PREFIX = "https://ccqspace.site/pd-rehab/assets/app-releases/"
MANIFEST_NAME = "latest-android.json"


class AndroidManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schemaVersion: int = Field(ge=1, le=1)
    packageName: Literal["com.pianoforparkinson.piano_practice"]
    versionName: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.-]+)?$", max_length=64)
    versionCode: int = Field(ge=1, le=2100000000)
    apkUrl: str
    sizeBytes: int = Field(ge=1, le=1024 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    notesZh: str = Field(max_length=2000)
    notesEn: str = Field(max_length=2000)


def _tool(name: str, args: list[str]) -> str:
    executable = os.environ.get(name, "")
    if not executable or not Path(executable).is_file():
        raise ValueError("APK verification tool unavailable")
    return subprocess.run([executable, *args], check=True, capture_output=True,
                          text=True, timeout=60).stdout


def inspect_apk(apk: Path, trusted_signer: str) -> dict:
    """Signature trust is supplied independently, never from a public manifest."""
    trust = trusted_signer.lower().replace(":", "")
    if not re.fullmatch(r"[a-f0-9]{64}", trust):
        raise ValueError("Original approved signer is required")
    certs = _tool("ANDROID_APKSIGNER", ["verify", "--verbose", "--print-certs", str(apk)])
    fingerprints = re.findall(r"certificate SHA-256 digest: ([a-fA-F0-9]+)", certs)
    if not fingerprints or any(value.lower() != trust for value in fingerprints):
        raise ValueError("APK signer does not match the original approved certificate")
    if re.search(r"certificate DN:.*(?:Android Debug|CN=debug)", certs, re.I):
        raise ValueError("Debug APK is not approved for public distribution")
    badging = _tool("ANDROID_AAPT", ["dump", "badging", str(apk)])
    package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
    sdk = re.search(r"sdkVersion:'(\d+)'", badging)
    if not package or package[1] != PACKAGE or not sdk or "application-debuggable" in badging:
        raise ValueError("APK package, minimum SDK or release flags are invalid")
    return dict(packageName=package[1], versionCode=int(package[2]),
                versionName=package[3], min_sdk=int(sdk[1]), signer_sha256=trust)


def apk_relative_path(url: str) -> Path:
    parsed = urlsplit(url)
    if (not url.startswith(PUBLIC_PREFIX) or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        raise ValueError("APK must be a direct same-origin HTTPS static file")
    relative = url[len(PUBLIC_PREFIX):]
    if not re.fullmatch(r"[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*\.apk", relative):
        raise ValueError("Unsafe APK path")
    path = Path(relative)
    if any(part in {".", ".."} for part in path.parts):
        raise ValueError("Unsafe APK path")
    return path


def verified_release() -> tuple[AndroidManifest, Path, dict] | None:
    """The administrator owns the immutable static directory; worker reads only.

    Presence of latest-android.json is the approved publication pointer. There
    is no competing stable.json or Shorebird requirement. No remote URLs are
    fetched, so redirects cannot replace the verified local artifact.
    """
    try:
        directory = settings._resolve(settings.android_release_dir)
        manifest_path = directory / MANIFEST_NAME
        if manifest_path.is_symlink():
            return None
        release = AndroidManifest.model_validate_json(manifest_path.read_bytes())
        relative = apk_relative_path(release.apkUrl)
        apk = directory / relative
        if any(part.is_symlink() for part in [apk, *apk.parents] if part != directory.parent):
            return None
        if not apk.is_file() or apk.stat().st_size != release.sizeBytes:
            return None
        with apk.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != release.sha256.lower():
                return None
        facts = inspect_apk(apk, settings.android_expected_signer_sha256)
        if any(getattr(release, key) != facts[key] for key in ("packageName", "versionName", "versionCode")):
            return None
        return release, apk, facts
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
