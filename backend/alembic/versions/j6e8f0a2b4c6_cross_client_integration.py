"""Add cross-client bindings, immutable record sync, face jobs and AI chat.

Revision ID: j6e8f0a2b4c6
Revises: i5d7e9f1a3b4
"""
from alembic import op
import sqlalchemy as sa
revision = "j6e8f0a2b4c6"
down_revision = "i5d7e9f1a3b4"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("device_patient_links",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("device_id",sa.String(100),nullable=False),
        sa.Column("local_profile_id",sa.String(100),nullable=False),sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id"),nullable=False),
        sa.Column("bound_by",sa.String(36),sa.ForeignKey("staff_users.id"),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.UniqueConstraint("device_id","local_profile_id",name="uq_device_profile"))
    op.create_index("ix_device_patient_links_device_id","device_patient_links",["device_id"])
    op.create_index("ix_device_patient_links_patient_id","device_patient_links",["patient_id"])
    op.create_table("external_practice_records",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id"),nullable=False),
        sa.Column("operator_id",sa.String(36),sa.ForeignKey("staff_users.id"),nullable=False),
        sa.Column("device_id",sa.String(100),nullable=False),sa.Column("source_record_id",sa.String(100),nullable=False),
        sa.Column("record_type",sa.String(40),nullable=False),sa.Column("schema_version",sa.String(32),nullable=False),
        sa.Column("task_version",sa.String(80)),sa.Column("metric_version",sa.String(80)),
        sa.Column("origin",sa.String(40),nullable=False),sa.Column("payload_sha256",sa.String(64),nullable=False),
        sa.Column("payload_json",sa.Text(),nullable=False),sa.Column("captured_at_ms",sa.BigInteger()),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.UniqueConstraint("device_id","source_record_id","record_type",name="uq_external_record_source"))
    op.create_index("ix_external_practice_records_patient_id","external_practice_records",["patient_id"])
    op.create_index("ix_external_practice_records_created_at","external_practice_records",["created_at"])
    op.create_index("ix_external_practice_records_record_type","external_practice_records",["record_type"])
    op.create_table("mobile_face_jobs",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id"),nullable=False),
        sa.Column("operator_id",sa.String(36),sa.ForeignKey("staff_users.id"),nullable=False),
        sa.Column("status",sa.String(32),nullable=False),sa.Column("stored_path",sa.String(512)),
        sa.Column("result_id",sa.String(36)),sa.Column("assessment_session_id",sa.String(36)),
        sa.Column("error_code",sa.String(80)),sa.Column("error_message",sa.String(500)),
        sa.Column("source_filename",sa.String(200)),sa.Column("size_bytes",sa.Integer(),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False))
    op.create_index("ix_mobile_face_jobs_patient_id","mobile_face_jobs",["patient_id"])
    op.create_table("expert_chat_turns",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("operator_id",sa.String(36),sa.ForeignKey("staff_users.id"),nullable=False),
        sa.Column("patient_id",sa.String(36),sa.ForeignKey("patients.id")),
        sa.Column("question",sa.Text(),nullable=False),sa.Column("answer",sa.Text(),nullable=False),
        sa.Column("model",sa.String(120),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_expert_chat_turns_operator_id","expert_chat_turns",["operator_id"])

def downgrade():
    for table in ["expert_chat_turns","mobile_face_jobs","external_practice_records","device_patient_links"]:
        op.drop_table(table)
