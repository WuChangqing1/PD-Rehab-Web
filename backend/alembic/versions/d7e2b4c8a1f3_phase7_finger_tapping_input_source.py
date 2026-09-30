"""phase7 finger tapping input_source provenance marker

Adds `finger_tapping_results.input_source` so the follow-up trend can tell a
patient recording from a test fixture or a seeded row.

The column defaults to `UNLABELLED`, and every row that already exists is left
UNLABELLED on purpose. Their provenance is genuinely unknown: a result only
records the media file it analysed, and the demo database contains at least one
row produced from `backend/tests/fixtures/finger_tapping_sample.mp4`. Guessing
`HUMAN_KEYBOARD` would have put a test fixture on a patient's progress chart, and
guessing `SEED_DEMO` would have been equally unfounded. Unlabelled rows are
excluded from trends and counted, which is the honest outcome.

Revision ID: d7e2b4c8a1f3
Revises: c3d9a1f7b2e8
Create Date: 2026-09-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e2b4c8a1f3"
down_revision: str | None = "c3d9a1f7b2e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("finger_tapping_results") as batch:
        batch.add_column(
            sa.Column(
                "input_source",
                sa.String(length=32),
                nullable=False,
                server_default="UNLABELLED",
            )
        )
        batch.create_index("ix_finger_tapping_results_input_source", ["input_source"])


def downgrade() -> None:
    with op.batch_alter_table("finger_tapping_results") as batch:
        batch.drop_index("ix_finger_tapping_results_input_source")
        batch.drop_column("input_source")
