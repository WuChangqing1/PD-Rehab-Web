"""Cross-client object access and durable mobile job state."""
from alembic import op
import sqlalchemy as sa
revision='k7f9a1b3c5d7'
down_revision='j6e8f0a2b4c6'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('patient_access_grants',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('patient_id',sa.String(36),sa.ForeignKey('patients.id'),nullable=False),
        sa.Column('staff_user_id',sa.String(36),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('patient_id','staff_user_id',name='uq_patient_staff_access'))
    op.create_index('ix_patient_access_grants_patient_id','patient_access_grants',['patient_id'])
    op.create_index('ix_patient_access_grants_staff_user_id','patient_access_grants',['staff_user_id'])
    op.add_column('device_patient_links',sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.add_column('external_practice_records',sa.Column('local_profile_id',sa.String(100)))
    for name,kind in [('device_id',sa.String(100)),('local_profile_id',sa.String(100)),('indices_json',sa.Text()),('candidates_json',sa.Text())]:
        op.add_column('mobile_face_jobs',sa.Column(name,kind))

def downgrade():
    for name in ['candidates_json','indices_json','local_profile_id','device_id']:op.drop_column('mobile_face_jobs',name)
    op.drop_column('external_practice_records','local_profile_id')
    op.drop_column('device_patient_links','active')
    op.drop_table('patient_access_grants')
