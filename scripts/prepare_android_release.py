"""Prepare a reviewed full-APK static bundle; never deploy or build an App."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.android_distribution import (  # noqa: E402
    AndroidManifest, MANIFEST_NAME, PUBLIC_PREFIX, inspect_apk,
)


def prepare_release(source: Path, output: Path, *, trusted_signer: str,
                    notes_zh: str, notes_en: str, approved: bool) -> dict:
    if not approved:
        raise ValueError("Explicit artifact approval is required; no manifest was written")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Source must be an existing regular APK")
    facts = inspect_apk(source, trusted_signer)
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    version = facts["versionName"]
    relative = Path(version) / f"qinban-{version}-android.apk"
    manifest = AndroidManifest(schemaVersion=1, packageName=facts["packageName"],
        versionName=version, versionCode=facts["versionCode"],
        apkUrl=PUBLIC_PREFIX + relative.as_posix(), sizeBytes=source.stat().st_size,
        sha256=digest, notesZh=notes_zh, notesEn=notes_en)
    # Validate the version before constructing any output paths.
    latest = output / MANIFEST_NAME
    if output.is_symlink() or latest.is_symlink():
        raise ValueError("Refusing symbolic output paths")
    if latest.exists():
        previous = AndroidManifest.model_validate_json(latest.read_bytes())
        if manifest.versionCode <= previous.versionCode:
            raise ValueError("versionCode must increase; rollback requires separate approval")
    destination = output / relative
    if destination.parent.is_symlink() or destination.is_symlink():
        raise ValueError("Refusing symbolic output paths")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an existing versioned APK, even if names match.
    with source.open("rb") as source_stream, destination.open("xb") as target:
        shutil.copyfileobj(source_stream, target)
    with destination.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError("Copied APK hash differs; manifest was not changed")
    staged = output / (MANIFEST_NAME + ".tmp")
    with staged.open("x", encoding="utf-8") as stream:
        stream.write(manifest.model_dump_json(indent=2) + "\n")
    staged.replace(latest)
    return manifest.model_dump()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-apk", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Local review bundle directory; this script does not deploy")
    parser.add_argument("--trusted-signer-sha256", required=True,
                        help="Independently verified original signing certificate fingerprint")
    parser.add_argument("--notes-zh", required=True)
    parser.add_argument("--notes-en", required=True)
    parser.add_argument("--approved-artifact", action="store_true")
    args = parser.parse_args()
    try:
        result = prepare_release(args.source_apk, args.output_dir,
            trusted_signer=args.trusted_signer_sha256, notes_zh=args.notes_zh,
            notes_en=args.notes_en, approved=args.approved_artifact)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Preparation stopped: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
