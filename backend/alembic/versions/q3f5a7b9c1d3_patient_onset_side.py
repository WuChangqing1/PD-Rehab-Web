"""Add onset_side to patients; historical rows stay UNKNOWN (not recorded).

Deliberately no backfill and no copy from affected_side: the onset side is a
separate clinical fact and must never be inferred from the current side.
"""
from alembic import op
import sqlalchemy as sa
revision='q3f5a7b9c1d3'
down_revision='p2e4f6a8b0c2'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('patients', sa.Column(
        'onset_side', sa.String(16), nullable=False, server_default='UNKNOWN'
    ))


def downgrade():
    op.drop_column('patients', 'onset_side')
