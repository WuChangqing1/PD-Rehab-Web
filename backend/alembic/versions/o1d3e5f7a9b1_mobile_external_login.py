"""Add external login without changing existing users, patient IDs or records."""
from alembic import op
import sqlalchemy as sa
from app.db.models.mobile_identity import MobileIdentity, MobileLoginChallenge, MobileAuthLimit

revision = 'o1d3e5f7a9b1'
down_revision = 'n0c2d4e6f8a0'
branch_labels = None
depends_on = None


def upgrade():
    for model in (MobileIdentity, MobileLoginChallenge, MobileAuthLimit):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # An unused installation can roll back normally. Once bindings exist, do
    # not silently remove users' account access paths.
    bind = op.get_bind()
    if bind.execute(sa.select(MobileIdentity.id).limit(1)).first() is not None:
        raise RuntimeError('Disable external login and preserve identity bindings; destructive downgrade is not supported.')
    for model in (MobileLoginChallenge, MobileAuthLimit, MobileIdentity):
        model.__table__.drop(bind, checkfirst=True)
