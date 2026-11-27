"""Add the self-reported age fallback to patients; historical rows stay empty.

birthday remains the only source of an exact age. age_years/age_recorded_on are
only used when the birth date is unknown; no birthday is fabricated and no
values are backfilled or inferred from existing rows.
"""
from alembic import op
import sqlalchemy as sa
revision='t5b7c9d1e3f5'
down_revision='s4a6b8c0d2e4'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('patients', sa.Column('age_years', sa.Integer(), nullable=True))
    op.add_column('patients', sa.Column('age_recorded_on', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('patients', 'age_recorded_on')
    op.drop_column('patients', 'age_years')
