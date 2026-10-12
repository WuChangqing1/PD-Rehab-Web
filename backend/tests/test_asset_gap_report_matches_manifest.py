"""The asset gap report must agree with the manifest it describes.

WHY THIS EXISTS
===============
`docs/upgrade-v2/asset_gap_report.md` carries a per-exercise table of the
demonstration-video situation, and `frontend/src/ballet/demoAssets.json` is the
register that actually decides what may play. The table had drifted from the
register in the worst direction: it described `SRC-PLIE-01` as 「已下载，未审核」
and quoted doc 04's *prediction* -- that the clip might not match the chair-supported
shallow-bend requirement -- as though the question were still open.

It had been answered. The clip was watched and rejected for patient use: no chair,
turned-out feet, a deeper bend than the definition allows. The manifest says so
(`status: CLIP_REVIEWED`), and section 4 of the same report already called it
错误素材. So section 3 and section 4 contradicted each other, and section 3 read as
"nobody has looked yet".

The cost is not cosmetic. It invites the next person to spend an afternoon
re-watching a clip that was already judged, and it misrepresents rejected material
as merely unreviewed.

Wording matters here and the report now states the distinction: 已看片 (watched,
done, rejected) and 动作审核 (clinical movement review, still outstanding) are
different things, and only the second is what the teacher owes.

Scope: this compares the report's status column against the register. It cannot
judge whether the prose is fair, and it does not try.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "upgrade-v2" / "asset_gap_report.md"
MANIFEST = ROOT / "frontend" / "src" / "ballet" / "demoAssets.json"

# Statuses in the register that mean "a person has looked at this and said no".
REJECTED_STATUSES = {"CLIP_REVIEWED"}


def _report_text() -> str:
    return REPORT.read_text(encoding="utf8")


def _manifest_entries() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf8"))["entries"]


def _status_rows() -> list[tuple[str, str, str]]:
    """(exercise, mode, status cell) for the rows of the per-exercise table."""
    rows: list[tuple[str, str, str]] = []
    for line in _report_text().splitlines():
        if not line.startswith("| `BALLET_"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        exercise = cells[0].strip("` ")
        mode = cells[1]
        status = cells[3]
        rows.append((exercise, mode, status))
    return rows


def test_the_report_still_has_the_per_exercise_table():
    rows = _status_rows()
    assert len(rows) == 9, f"expected nine action-by-mode rows, found {len(rows)}"


def test_every_row_matches_the_register():
    by_key = {(e["exercise_key"], e["execution_mode"]): e for e in _manifest_entries()}
    problems: list[str] = []

    for exercise, mode, status in _status_rows():
        entry = by_key.get((exercise, mode))
        if entry is None:
            problems.append(f"{exercise}/{mode}: not in the register at all")
            continue

        registered = entry.get("status", "")
        # A rejected or reviewed clip must not be described as unreviewed.
        if registered in REJECTED_STATUSES and "未审核" in status:
            problems.append(
                f"{exercise}/{mode}: the register says {registered} and records a "
                f"rejection, but the report still calls it {status!r}"
            )
        # And a row that claims a candidate exists must have one in the register.
        if "已下载" in status and registered == "NOT_SELECTED":
            problems.append(
                f"{exercise}/{mode}: the report claims a downloaded candidate, the "
                "register has none"
            )

    assert not problems, "the asset report has drifted from the register:\n  " + "\n  ".join(
        problems
    )


def test_the_rejected_clip_is_still_recorded_as_rejected_in_the_register():
    """If this stops being true, the report's rejection claim must be revisited."""
    rejected = [
        e for e in _manifest_entries() if e.get("status") in REJECTED_STATUSES
    ]
    assert rejected, (
        "no entry carries a reviewed status any more. Either the register was reset "
        "or the rejection was undone; in both cases the report's wording is now "
        "unverified and this test should be rewritten alongside it."
    )
    for entry in rejected:
        assert entry.get("notes"), (
            f"{entry['exercise_key']} is marked {entry['status']} with no note saying "
            "why, so nobody can tell what was concluded"
        )


def test_the_report_distinguishes_watching_from_clinical_review():
    """The two must not be conflated: only the second is outstanding."""
    text = _report_text()
    assert "已看片" in text, "the report should name the act of watching a clip"
    assert "动作审核" in text, "the report should name the clinical review separately"
    assert re.search(r"两件事|不同", text), (
        "the report should state that watching and clinical review are different, so "
        "a rejected clip is not read as an unreviewed one"
    )


def test_no_row_claims_a_candidate_is_awaiting_retry_after_it_was_abandoned():
    """The Tendu download failed on three networks; 'waiting to retry' overstates it.

    Checked against the status cell only. The row's explanation deliberately quotes
    the old wording to say it is wrong -- 不是"待重试"，是当前拿不到 -- and an
    assertion over the whole line would flag that correction as the error.
    """
    # Only the standing row ever had a candidate; the seated variant has none.
    for exercise, mode, status in _status_rows():
        if exercise != "BALLET_TENDU" or mode != "STANDING_SUPPORTED":
            continue
        assert "待重试" not in status, (
            "the Tendu candidate is unreachable from three networks, not queued for a "
            f"retry, but the status still reads {status!r}"
        )
        assert "取不到" in status, (
            "the standing Tendu row should say the candidate cannot be obtained, not "
            f"that one is missing: {status!r}"
        )
