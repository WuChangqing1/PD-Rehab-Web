"""deactivate piano baselines that did not come from a person

A piano calibration whose key events came from a script was able to become the
patient's ACTIVE baseline. It then read as measured ability everywhere: the
training hub said "基础能力测试已完成" and dated it, the difficulty engine scaled the
patient's training from it, and the report showed its numbers.

This was not hypothetical. On the deployed database the active baseline for one
patient -- accuracy 0.778, reaction latency 732 ms, CV 0.031 -- came from a single
`SYNTHETIC_SELFTEST` calibration, while the three real `HUMAN_KEYBOARD`
calibrations on that database were all incomplete. The snapshot did carry a
warning note and the API returned it, but nothing displayed it, so every screen
presented a machine's rhythm as the patient's own.

The code fix (`save_calibration_baseline` now writes `is_active=is_human`) stops
this happening again. This migration corrects the rows that already exist.

WHAT IT DOES
------------
Sets `is_active = 0` on PIANO_CALIBRATION baselines whose source session is not
marked HUMAN_KEYBOARD. The rows are NOT deleted: the run happened, it is part of
the audit trail, and its snapshot keeps the reason it cannot be used. Only the
claim that it represents the patient's ability is withdrawn.

After this, the affected patients read as "not yet measured", which is true, and
a real calibration produces a real baseline.

DOWNGRADE
---------
Deliberately a no-op. Reactivating these rows would restore the defect, and there
is no safe way to tell which of them had been active before. A downgrade that
silently re-published synthetic measurements as clinical baselines would be worse
than one that does nothing and says so.

Revision ID: g3b5c7d9e1f2
Revises: f2a4b6c8d0e1
Create Date: 2026-10-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g3b5c7d9e1f2"
down_revision: str | None = "f2a4b6c8d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # Which baselines are affected, before changing anything, so the operation is
    # auditable in the migration log rather than silently mutating rows.
    affected = bind.execute(
        sa.text(
            """
            SELECT b.id, b.patient_id, s.input_source
            FROM baselines b
            JOIN piano_sessions s ON s.id = b.source_id
            WHERE b.baseline_type = 'PIANO_CALIBRATION'
              AND b.is_active = 1
              AND s.input_source != 'HUMAN_KEYBOARD'
            """
        )
    ).fetchall()

    if affected:
        print(f"  deactivating {len(affected)} non-human piano baseline(s):")
        for row in affected:
            print(f"    baseline {str(row[0])[:8]}  patient {str(row[1])[:8]}  source={row[2]}")
    else:
        print("  no non-human piano baselines are active; nothing to change")

    bind.execute(
        sa.text(
            """
            UPDATE baselines
            SET is_active = 0
            WHERE baseline_type = 'PIANO_CALIBRATION'
              AND is_active = 1
              AND source_id IN (
                  SELECT id FROM piano_sessions WHERE input_source != 'HUMAN_KEYBOARD'
              )
            """
        )
    )


def downgrade() -> None:
    # See the module docstring: reactivating would restore the defect, and the
    # previous active/inactive split cannot be reconstructed safely.
    print("  downgrade is intentionally a no-op; see the migration docstring")
