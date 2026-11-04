"""Index cross-client changes without altering practice or assessment tables."""
from alembic import op
from app.services.sync_changes import install, uninstall

revision = 'm9b1c3d5e7f9'
down_revision = 'l8a0b2c4d6e8'
branch_labels = None
depends_on = None


def upgrade():
    install(op.get_bind())


def downgrade():
    uninstall(op.get_bind())
