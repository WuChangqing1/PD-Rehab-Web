"""Resumable training video parents, without changing native practice records."""
from alembic import op
import sqlalchemy as sa
revision = 'l8a0b2c4d6e8'
down_revision = 'k7f9a1b3c5d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('face_recordings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('patient_id', sa.String(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('operator_id', sa.String(36), sa.ForeignKey('staff_users.id'), nullable=False),
        sa.Column('device_id', sa.String(100), nullable=False),
        sa.Column('local_profile_id', sa.String(100), nullable=False),
        sa.Column('client_capture_id', sa.String(36), nullable=False),
        sa.Column('external_record_id', sa.String(36), sa.ForeignKey('external_practice_records.id'), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('manifest_sha256', sa.String(64), nullable=False),
        sa.Column('data_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('device_id', 'client_capture_id', name='uq_face_capture_source'))
    for column in ['patient_id', 'external_record_id', 'status']:
        op.create_index('ix_face_recordings_' + column, 'face_recordings', [column])


def downgrade():
    op.drop_table('face_recordings')
