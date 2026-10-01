"""phase8 ballet execution_mode

Adds `pose_sessions.execution_mode` so a recorded exercise states whether the
patient performed it seated or standing with support.

The exercise set itself changed in the same release (five yoga poses -> five
ballet exercises), but that is data, not schema: `exercise_type` already holds a
free string and historical rows keep the key they were performed under.

Existing rows are backfilled to `UNKNOWN` rather than to either real mode. The
same joint angles measured seated and standing describe different tasks, so
picking one for rows that never recorded it would be an invention. `UNKNOWN` is
excluded from mode-specific comparisons.

Revision ID: e8f1a3c5b7d9
Revises: d7e2b4c8a1f3
Create Date: 2026-10-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1a3c5b7d9"
down_revision: str | None = "d7e2b4c8a1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pose_sessions") as batch:
        batch.add_column(
            sa.Column(
                "execution_mode",
                sa.String(length=24),
                nullable=False,
                server_default="UNKNOWN",
            )
        )
        batch.create_index("ix_pose_sessions_execution_mode", ["execution_mode"])

    # The retired yoga exercises were all performed standing, which the doctor
    # declared nowhere. Marking them by exercise key would be a guess about the
    # patient, so they stay UNKNOWN and the UI simply does not show a mode for
    # them.
    op.execute(
        """
        UPDATE pose_sessions
           SET execution_mode = 'UNKNOWN'
         WHERE exercise_type IN (
             'MOUNTAIN_ARMS_UP',
             'ARMS_LATERAL_RAISE',
             'SIDE_BEND_STRETCH',
             'SEATED_TRUNK_ROTATION',
             'SEATED_ALTERNATING_ARM_RAISE'
         )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("pose_sessions") as batch:
        batch.drop_index("ix_pose_sessions_execution_mode")
        batch.drop_column("execution_mode")
