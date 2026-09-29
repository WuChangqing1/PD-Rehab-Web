"""phase6 pose session provenance, quality and source recording

`pose_sessions` existed from Phase 1 with the metric columns but nothing to run
them. Phase 6 adds what the analysis needs to be trustworthy:

  * input_source   -- the same provenance marker piano_sessions got, so a
                      recording that is not a real patient cannot be read as a
                      measurement
  * quality_json   -- frame counts, valid ratio, landmark visibility and the
                      gates that failed, stored whether or not the analysis was
                      accepted
  * media_file_id  -- the uploaded recording the numbers came from

Revision ID: c3d9a1f7b2e8
Revises: b1c7f0a2d4e5
Create Date: 2026-09-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d9a1f7b2e8"
down_revision: str | None = "b1c7f0a2d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pose_sessions") as batch:
        batch.add_column(
            sa.Column(
                "input_source",
                sa.String(length=32),
                nullable=False,
                server_default="HUMAN_KEYBOARD",
            )
        )
        batch.add_column(sa.Column("quality_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("media_file_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_pose_sessions_input_source", ["input_source"])
        batch.create_foreign_key(
            "fk_pose_sessions_media_file_id",
            "media_files",
            ["media_file_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Existing rows predate any analysis: the seeder wrote randomised values and
    # no recording exists. Mark them so they cannot be mistaken for measurements.
    op.execute(
        """
        UPDATE pose_sessions
           SET input_source = 'SEED_DEMO'
         WHERE completed_at IS NOT NULL
           AND media_file_id IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("pose_sessions") as batch:
        batch.drop_constraint("fk_pose_sessions_media_file_id", type_="foreignkey")
        batch.drop_index("ix_pose_sessions_input_source")
        batch.drop_column("media_file_id")
        batch.drop_column("quality_json")
        batch.drop_column("input_source")
