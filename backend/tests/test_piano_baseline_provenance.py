"""A synthetic calibration must not become the patient's baseline.

WHY THIS EXISTS
===============
This was found on the deployed database rather than in code review. The patient's
active piano baseline -- accuracy 0.778, reaction latency 732 ms, CV 0.031 -- came
from a single `SYNTHETIC_SELFTEST` calibration. The three real `HUMAN_KEYBOARD`
calibrations on that database were all incomplete, so the synthetic run was the
only candidate and it won by default.

Every screen then presented it as measured ability: the training hub said
"基础能力测试已完成" and gave the date, and the piano page scaled the patient's
training from it. The snapshot did carry a warning note, and the API returned it,
but nothing displayed it.

The route into this was not exotic. The app accepts `?selftest=1`, which marks a
round SYNTHETIC_SELFTEST, and a calibration run that way on a real patient would
silently replace their baseline.

These tests pin the rule at the level where it is decided: `is_active`.
"""

from __future__ import annotations

import inspect

from app.services import piano_service


def _source() -> str:
    return inspect.getsource(piano_service.save_calibration_baseline)


def test_the_baseline_is_only_active_for_human_input():
    src = _source()
    # The gate must exist and must key on the provenance marker.
    assert "is_active=is_human" in src, (
        "the baseline is no longer gated on provenance; a synthetic calibration "
        "can become the patient's active baseline again"
    )
    assert 'is_human = session.input_source == "HUMAN_KEYBOARD"' in src


def test_a_non_human_baseline_is_still_stored_but_warned_about():
    src = _source()
    # The row is kept: the flow test is a real record of a run, and deleting it
    # would lose the audit trail.
    assert "db.add(baseline)" in src
    # And storing it silently would hide the reason it is inactive.
    assert "logger.warning" in src
    assert "INACTIVE" in src


def test_the_stored_snapshot_still_carries_the_provenance_note():
    src = _source()
    assert "不是真人测量值" in src
    assert "不得作为临床或科研基线使用" in src
    # Both branches exist, so a human baseline is not labelled as synthetic.
    assert "数值来自真实训练事件" in src


def test_only_a_human_calibration_satisfies_the_active_lookup():
    # `active_calibration` reads `is_active`; the gate above is what keeps a
    # synthetic row out of it. This asserts the two are still connected, so a
    # future change to the lookup cannot quietly bypass the gate.
    lookup = inspect.getsource(piano_service.active_calibration)
    assert "Baseline.is_active.is_(True)" in lookup
    assert 'Baseline.baseline_type == "PIANO_CALIBRATION"' in lookup


def test_previous_baselines_are_deactivated_not_deleted():
    # Spec V2 section 33: history is kept.
    src = _source()
    assert "row.is_active = False" in src
    assert "db.delete" not in src
