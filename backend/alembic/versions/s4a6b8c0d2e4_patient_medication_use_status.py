"""Add medication_use_status to patients; historical rows stay UNKNOWN.

Deliberately no backfill and no inference from medication_state: an OFF period
does not mean the patient is not taking PD-related medication, so the two
fields must stay independent and historical rows remain "not recorded".
"""
from alembic import op
import sqlalchemy as sa
revision='s4a6b8c0d2e4'
down_revision='q3f5a7b9c1d3'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('patients', sa.Column(
        'medication_use_status', sa.String(16), nullable=False, server_default='UNKNOWN'
    ))


def downgrade():
    op.drop_column('patients', 'medication_use_status')
