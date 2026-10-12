"""The application only ever consumes provenance-gated baselines.

WHY THIS EXISTS
===============
The provenance audit (`docs/upgrade-v2/provenance_audit.md`) found ten
COMPREHENSIVE baseline rows in the production database, all active, all written by
the demo seed script and all marked `{"source": "seed_demo", "synthetic": true}` in
their snapshot. They are currently harmless because **no code path reads them**:
the backend only ever queries `baseline_type == "PIANO_CALIBRATION"`, and the
frontend only calls the piano baseline endpoint.

That is a fact about today's code, and it is exactly the kind of fact that stops
being true by accident. The moment someone implements "establish a baseline from a
comprehensive assessment" and copies the obvious query -- fetch the active row for
this patient -- a seeded or synthetic baseline becomes the patient's measured
ability, which is the defect already found once on the piano path.

These tests do not forbid adding comprehensive baselines. They require that the
read path is provenance-gated before it reaches a patient's screen, by failing if
a new baseline type starts being read without a gate.

Scope note: these are source assertions, not behavioural ones. They read the
service module and the frontend API surface, which is where the decision lives.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from app.services import piano_service

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_API = ROOT / "frontend" / "src" / "api" / "index.ts"
PANEL_SERVICE = ROOT / "backend" / "app" / "services"


def _service_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf8")
        for path in PANEL_SERVICE.glob("*.py")
    }


def test_only_the_piano_baseline_type_is_queried_by_the_backend():
    hits: list[str] = []
    for name, text in _service_sources().items():
        for line in text.splitlines():
            if "baseline_type" not in line:
                continue
            # Comments explain the rule; only code counts.
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            hits.append(f"{name}: {stripped}")

    assert hits, "expected the baseline lookups to be found at all"

    for hit in hits:
        assert "PIANO_CALIBRATION" in hit, (
            "a baseline type other than PIANO_CALIBRATION is now being queried. "
            "Before it can be shown to a patient it needs its own provenance gate: "
            "a baseline whose source was not a real measurement must not be active, "
            "and a stored warning is not a substitute. See "
            f"docs/upgrade-v2/provenance_audit.md section 6. Offending line -> {hit}"
        )


def test_the_piano_lookup_is_the_one_that_carries_the_gate():
    # The gate and the lookup must stay in the same module, so a copy of the
    # lookup into a new module cannot silently arrive without the gate.
    lookup = inspect.getsource(piano_service.active_calibration)
    assert "Baseline.is_active.is_(True)" in lookup

    gate = inspect.getsource(piano_service.save_calibration_baseline)
    assert "is_active=is_human" in gate
    assert 'is_human = session.input_source == "HUMAN_KEYBOARD"' in gate


def test_the_frontend_has_exactly_one_baseline_endpoint():
    api = FRONTEND_API.read_text(encoding="utf8")
    baseline_calls = [
        line.strip() for line in api.splitlines() if "/baseline" in line
    ]
    assert len(baseline_calls) == 1, (
        "a second baseline endpoint appeared in the API client. Any new baseline "
        f"surface must be provenance-gated first. Found -> {baseline_calls}"
    )
    assert "piano/baseline" in baseline_calls[0]


def test_the_seed_script_still_labels_its_synthetic_baselines():
    # The seeded baselines are only tolerable because they say what they are. If
    # the marker is dropped the rows become indistinguishable from real ones in
    # the one place a future reader would look.
    seed = (ROOT / "scripts" / "seed_demo.py").read_text(encoding="utf8")
    if "Baseline(" not in seed:
        return  # the seed script no longer writes baselines at all
    assert "synthetic" in seed, (
        "the seed script writes baselines without marking them synthetic"
    )
    assert "seed_demo" in seed
