"""phase5 piano input_source provenance marker

Adds `piano_sessions.input_source` so a row can always declare where its key
events came from: HUMAN_KEYBOARD, SYNTHETIC_SELFTEST or SEED_DEMO.

Rows created before this migration are backfilled to SEED_DEMO when they have no
raw events, because a real round cannot complete without storing its events;
everything else stays HUMAN_KEYBOARD rather than being guessed at.

Revision ID: b1c7f0a2d4e5
Revises: 69a1df545cdc
Create Date: 2026-09-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c7f0a2d4e5"
down_revision: str | None = "69a1df545cdc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("piano_sessions") as batch:
        batch.add_column(
            sa.Column(
                "input_source",
                sa.String(length=32),
                nullable=False,
                server_default="HUMAN_KEYBOARD",
            )
        )
        batch.create_index("ix_piano_sessions_input_source", ["input_source"])

    # A real round always stores its raw events before completing, so a
    # completed session with no events can only have been seeded.
    op.execute(
        """
        UPDATE piano_sessions
           SET input_source = 'SEED_DEMO'
         WHERE completed_at IS NOT NULL
           AND id NOT IN (SELECT DISTINCT session_id FROM piano_events)
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("piano_sessions") as batch:
        batch.drop_index("ix_piano_sessions_input_source")
        batch.drop_column("input_source")
