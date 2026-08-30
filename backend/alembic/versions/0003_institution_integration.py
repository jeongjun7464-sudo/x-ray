"""institution integration tables

Revision ID: 0003_institution_integration
Revises: 0002_audit_events
"""
from alembic import op
import sqlalchemy as sa

revision="0003_institution_integration"; down_revision="0002_audit_events"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("studies",sa.Column("id",sa.String(36),primary_key=True),sa.Column("anonymous_accession",sa.String(64)),sa.Column("study_uid_hash",sa.String(64),nullable=False,unique=True),sa.Column("study_date",sa.String(16)),sa.Column("region",sa.String(32),nullable=False),sa.Column("protocol_status",sa.String(32),nullable=False),sa.Column("views",sa.JSON(),nullable=False),sa.Column("tags",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("study_instances",sa.Column("id",sa.String(36),primary_key=True),sa.Column("study_id",sa.String(36),nullable=False),sa.Column("series_uid_hash",sa.String(64),nullable=False),sa.Column("sop_uid_hash",sa.String(64),nullable=False,unique=True),sa.Column("series_number",sa.Integer()),sa.Column("instance_number",sa.Integer()),sa.Column("view_position",sa.String(16),nullable=False),sa.Column("laterality",sa.String(16),nullable=False),sa.Column("prediction_id",sa.String(36)))
    op.create_table("protocol_definitions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("region",sa.String(32),nullable=False,unique=True),sa.Column("required_views",sa.JSON(),nullable=False),sa.Column("optional_views",sa.JSON(),nullable=False),sa.Column("active",sa.Boolean(),nullable=False),sa.Column("version",sa.String(32),nullable=False))
    op.create_table("code_mappings",sa.Column("id",sa.String(36),primary_key=True),sa.Column("internal_code",sa.String(32),nullable=False,unique=True),sa.Column("korean_name",sa.String(64),nullable=False),sa.Column("english_name",sa.String(64),nullable=False),sa.Column("snomed_ct",sa.String(64)),sa.Column("radlex",sa.String(64)),sa.Column("dicom_body_part",sa.String(64)),sa.Column("active",sa.Boolean(),nullable=False),sa.Column("version",sa.String(32),nullable=False))
    op.create_table("routing_rules",sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(100),nullable=False),sa.Column("priority",sa.Integer(),nullable=False),sa.Column("conditions",sa.JSON(),nullable=False),sa.Column("destination",sa.String(64),nullable=False),sa.Column("active",sa.Boolean(),nullable=False),sa.Column("version",sa.String(32),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("integration_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("event_type",sa.String(64),nullable=False),sa.Column("payload",sa.JSON(),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("attempts",sa.Integer(),nullable=False),sa.Column("next_attempt_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for name in ("integration_events","routing_rules","code_mappings","protocol_definitions","study_instances","studies"): op.drop_table(name)
