"""Add isolated guided song sessions without modifying existing training data."""
from alembic import op
import sqlalchemy as sa

revision='h4c6d8e0f2a3'
down_revision='g3b5c7d9e1f2'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('guided_song_sessions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('patient_id',sa.String(36),sa.ForeignKey('patients.id'),nullable=False),
        sa.Column('owner_id',sa.String(36),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('client_request_id',sa.String(128),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('config',sa.JSON(),nullable=False),
        sa.Column('events',sa.JSON(),nullable=False),
        sa.Column('result',sa.JSON(),nullable=False),
        sa.Column('audio',sa.LargeBinary(),nullable=True),
        sa.Column('audio_metadata',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('completed_at',sa.DateTime(),nullable=True),
        sa.UniqueConstraint('owner_id','client_request_id'))
    op.create_index('ix_guided_song_sessions_patient_id','guided_song_sessions',['patient_id'])
    op.create_index('ix_guided_song_sessions_owner_id','guided_song_sessions',['owner_id'])


def downgrade():
    op.drop_table('guided_song_sessions')
