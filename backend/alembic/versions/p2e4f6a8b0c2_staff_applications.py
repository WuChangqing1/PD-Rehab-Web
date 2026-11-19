"""Add pending staff applications; preserve all existing accounts and clinical rows."""
from alembic import op
import sqlalchemy as sa
from app.db.models.staff_application import StaffApplication
revision='p2e4f6a8b0c2'
down_revision='o1d3e5f7a9b1'
branch_labels=None
depends_on=None

def upgrade():
    StaffApplication.__table__.create(op.get_bind(),checkfirst=True)

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.select(StaffApplication.id).limit(1)).first():
        raise RuntimeError('Preserve staff applications before downgrade.')
    StaffApplication.__table__.drop(bind,checkfirst=True)
