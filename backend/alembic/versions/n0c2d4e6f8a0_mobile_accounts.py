"""Patient registration and revocable mobile sessions; preserves existing data."""
from alembic import op
from sqlalchemy import text
from app.db.models.mobile_account import MobileAccount, MobileSession

revision = 'n0c2d4e6f8a0'
down_revision = 'm9b1c3d5e7f9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    MobileAccount.__table__.create(bind, checkfirst=True)
    MobileSession.__table__.create(bind, checkfirst=True)


def downgrade():
    # Older staff-only code does not understand PATIENT permissions. Retain the
    # rows and training data, but disable these logins before removing guards.
    op.get_bind().execute(text("UPDATE staff_users SET is_active=0 WHERE role='PATIENT'"))
    MobileSession.__table__.drop(op.get_bind(), checkfirst=True)
    MobileAccount.__table__.drop(op.get_bind(), checkfirst=True)
