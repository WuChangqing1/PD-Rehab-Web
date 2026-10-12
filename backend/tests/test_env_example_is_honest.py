"""Every key in .env.example must be one the code actually reads, or say so.

WHY THIS EXISTS
===============
`.env.example` documented twelve Finger Tapping thresholds -- filter cutoff, peak
distance, cycle-count floor and the rest -- under a heading describing them as the
tunable analysis parameters, with a note that they must be recorded for
reproducibility. They were read by nothing at all. The values that actually apply
live as constants in `adapter.py` and `features.py`, and the only reference to any
of those names anywhere in the repository was a comment.

The reproducibility half was true: the values really are written into each
result's `analysis_config_json`. The tunability half was not, and nothing said so.
An operator who lowered the cutoff to smooth a noisy recording would see no change
and no error, and would reasonably conclude the pipeline ignored the setting.

That is the same shape as the other defects found in this project -- a fact the
system asserts and does not act on -- so it gets the same treatment: make the
document say what is true, and fail the build if it drifts again.

The check is deliberately narrow. It cannot tell whether a key has an *effect*,
only whether its name appears in the source at all. That is enough to catch a key
wired to nothing, which is the failure mode here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / ".env.example"

# Keys that are legitimately absent from the source, with the reason. Anything not
# listed here has to be referenced somewhere in backend/app or frontend/src.
ALLOWED_UNREFERENCED: dict[str, str] = {
    # Consumed by the deployment tooling and nginx, not by the application.
    "PD_REHAB_BASE",
}

SOURCE_SUFFIXES = (".py", ".ts", ".vue", ".mjs", ".sh")


def _example_keys() -> list[tuple[str, bool]]:
    """Return (key, declared_not_read) for every key in the file.

    A key is "declared not read" when the heading that introduces its block says
    so. That is an acceptable state -- a documented value that the code does not
    consume is fine as long as the file says as much; what is not acceptable is a
    key presented as a working knob while nothing reads it.
    """
    lines = EXAMPLE.read_text(encoding="utf8").splitlines()
    out: list[tuple[str, bool]] = []
    header: list[str] = []

    for line in lines:
        if line.lstrip().startswith("#"):
            header.append(line)
            continue
        match = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=", line)
        if match:
            declared = any(
                marker in h for h in header for marker in ("不会生效", "尚未读取", "not read")
            )
            out.append((match.group(1), declared))
        elif line.strip():
            # A non-comment, non-key line ends the block's heading context.
            header = []
    return out


def _source_text() -> str:
    chunks: list[str] = []
    for base in (ROOT / "backend" / "app", ROOT / "frontend" / "src"):
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            chunks.append(path.read_text(encoding="utf8", errors="replace"))
    return "\n".join(chunks)


def test_env_example_exists_and_is_not_empty():
    assert EXAMPLE.is_file(), ".env.example is linked from the README and must exist"
    assert len(_example_keys()) > 20, "expected a substantial example file"


def test_every_documented_key_is_either_read_or_declared_inert():
    source = _source_text().lower()

    problems: list[str] = []
    for key, declared_not_read in _example_keys():
        if key in ALLOWED_UNREFERENCED or declared_not_read:
            continue
        if key.lower() in source:
            continue
        problems.append(key)

    assert not problems, (
        "these keys are documented in .env.example as working settings, but appear "
        "nowhere in the application source. Setting them can have no effect, and "
        "nothing tells the reader that. Either wire them up, delete them, or state "
        "in the block heading that the code does not read them yet:\n  "
        + "\n  ".join(problems)
    )


def test_at_least_one_key_is_declared_inert_so_the_escape_hatch_is_real():
    """If the exemption is ever unused the parsing above has silently broken."""
    declared = [k for k, inert in _example_keys() if inert]
    assert declared, (
        "expected the Finger Tapping threshold block to be declared as not read; "
        "if that marker is gone, either the keys were wired up (then delete this "
        "test) or the declaration was removed (then the keys are misleading again)"
    )


def test_the_finger_tapping_thresholds_declare_that_they_are_not_read():
    """The specific group that was wrong must keep saying so."""
    text = EXAMPLE.read_text(encoding="utf8")
    block_start = text.find("FT_NORMALIZATION_METHOD")
    assert block_start > 0, "expected the threshold block to still exist"

    # Walk back to the heading that introduces it.
    heading_start = text.rfind("# ----------", 0, block_start)
    header = text[heading_start:block_start]

    assert "不会生效" in header or "尚未读取" in header, (
        "the threshold block must state that the code does not read these values. "
        "Twelve keys were documented as tunable while nothing read them, and an "
        "operator changing one would see no effect and no error."
    )
    assert "analysis_config_json" in header, (
        "the header should keep the part that IS true: the effective values are "
        "recorded per result, so a single analysis stays reproducible"
    )


def test_the_version_keys_are_still_real_settings():
    """Guard the distinction: the version keys in the same section DO work."""
    from app.core.config import settings

    assert settings.ft_feature_algorithm_version
    assert settings.ft_qc_algorithm_version
    assert settings.ft_compare_algorithm_version
