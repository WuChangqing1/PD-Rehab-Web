"""Display scores stay empty; nothing invents a number to fill a card.

WHY THIS EXISTS
===============
D08 in `docs/upgrade-v2/spec_decisions.md` records the decision: the presentation
scores -- completion, range of motion, symmetry, stability -- stay NULL, the raw
measurements are shown instead, and the card footnote explains why. The brief
forbids generating random 0-100 values, and the upstream model that would supply a
severity classification does not exist.

The decision currently holds: those columns are assigned `None` explicitly in
`pose_service.py`, `severity_score` and `severity_label` come from an analysis
outcome that never produces a value, and every row in the development database has
them empty. The frontend says so in two places.

It holds because the assignments say `None`, which is a fragile way to guarantee
something. A single well-meaning edit that fills the field to make a card look
complete would satisfy every existing test -- none of them look at these columns --
and would put an invented clinical number in front of a doctor. Hence this file.

Scope: it checks that the only values ever assigned are `None`, and that the UI
still tells the reader why the fields are blank. It cannot check the upstream
model's behaviour, and it does not try.
"""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"

# Columns that must never carry an invented value.
POSE_SCORES = ("completion_score", "range_of_motion", "symmetry_score", "stability_score")
SEVERITY_FIELDS = ("severity_score", "severity_label")


def _python_sources() -> list[Path]:
    return [
        p
        for p in APP.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "models.py"
    ]


def _assignments(field: str) -> list[tuple[str, str]]:
    """Every `field = value` in the application, as (file, value_source)."""
    pattern = re.compile(rf"\b{re.escape(field)}\s*=\s*([^,\n\)]+)")
    found: list[tuple[str, str]] = []
    for path in _python_sources():
        for match in pattern.finditer(path.read_text(encoding="utf8")):
            found.append((path.name, match.group(1).strip()))
    return found


def test_pose_display_scores_are_only_ever_assigned_none():
    for field in POSE_SCORES:
        assignments = _assignments(field)
        assert assignments, (
            f"{field} is never assigned anywhere. If the column was removed, delete "
            "it from this test; if the assignment moved, point the test at it."
        )
        for where, value in assignments:
            assert value == "None", (
                f"{where} assigns {field} = {value}. The display scores are "
                "deliberately empty because no formula is defined for them "
                "(spec_decisions.md D08); filling one in would put an invented "
                "clinical number in front of a doctor."
            )


def test_severity_comes_from_the_pipeline_and_the_pipeline_has_no_model():
    """`severity_score` may be forwarded, but only from a source that yields None.

    It is not assigned a constant, so the guarantee rests on the analysis pipeline
    having no severity classifier. That is asserted by the model registry rather
    than by this file, so here we only require that the value is forwarded, never
    synthesised.
    """
    assignments = _assignments("severity_score")
    assert assignments, "expected severity_score to be written somewhere"
    for where, value in assignments:
        assert not re.fullmatch(r"[\d.]+", value), (
            f"{where} assigns severity_score a literal number ({value}). There is no "
            "severity model; a hardcoded score is fabricated clinical data."
        )
        assert "outcome" in value or value == "None", (
            f"{where} assigns severity_score from {value!r}. It should come from the "
            "analysis outcome, which produces None while no model is configured."
        )


def test_the_interface_explains_why_the_scores_are_blank():
    """An empty field with no explanation reads as a bug, so the note is required."""
    page = (FRONTEND / "pages" / "MovementTrainingPage.vue").read_text(encoding="utf8")
    assert "展示分" in page, "the movement page should name the display scores"
    assert "公式未定义" in page or "为空" in page, (
        "the page must say the display scores are blank because no formula exists, "
        "rather than leaving the reader to guess"
    )


def test_no_random_or_placeholder_score_helpers_exist():
    """A helper that manufactures a score would defeat everything above."""
    suspicious = re.compile(
        r"def\s+\w*(?:fake|dummy|placeholder|mock)\w*_?(?:score|metric)",
        re.IGNORECASE,
    )
    offenders = [
        f"{path.name}: {m.group(0)}"
        for path in _python_sources()
        for m in suspicious.finditer(path.read_text(encoding="utf8"))
    ]
    assert not offenders, "found a helper that looks like it fabricates scores: " + "; ".join(
        offenders
    )
