"""phase9 piano training recipe

Adds `piano_sessions.recipe_id` so a round records which training recipe it ran
under, alongside the `mode` that says which cue generator produced it.

A recipe is a template over an existing mode, not a second engine (docs/05), so
both are needed: `mode` alone cannot tell an SFT round from a CFT round, because
both build on modes the platform already had.

NULLABLE ON PURPOSE. Every row recorded before this migration, and every round run
on a plain mode, has no recipe. Backfilling a value would misdescribe those
sessions, and reports must not average different recipes together -- a null is the
honest answer for "this round did not belong to a recipe", and it keeps the
existing `mode`-based grouping working unchanged.

Existing rows are left untouched. No metric column changes, so every historical
score stays exactly as it was computed.

Revision ID: f2a4b6c8d0e1
Revises: e8f1a3c5b7d9
Create Date: 2026-10-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a4b6c8d0e1"
down_revision: str | None = "e8f1a3c5b7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "piano_sessions",
        sa.Column("recipe_id", sa.String(length=48), nullable=True),
    )
    op.create_index(
        "ix_piano_sessions_recipe_id",
        "piano_sessions",
        ["recipe_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_piano_sessions_recipe_id", table_name="piano_sessions")
    op.drop_column("piano_sessions", "recipe_id")
