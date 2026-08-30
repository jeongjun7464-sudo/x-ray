"""AI validation, labeling and CAPA tables

Revision ID: 0004_ai_validation
Revises: 0003_institution_integration
"""
from alembic import op
import sqlalchemy as sa
revision="0004_ai_validation";down_revision="0003_institution_integration";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("pipeline_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("input_hash",sa.String(64),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("final_route",sa.String(64)),sa.Column("stages",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("label_tasks",sa.Column("id",sa.String(36),primary_key=True),sa.Column("image_hash",sa.String(64),nullable=False),sa.Column("assignee",sa.String(64)),sa.Column("status",sa.String(32),nullable=False),sa.Column("first_review",sa.JSON()),sa.Column("second_review",sa.JSON()),sa.Column("final_label",sa.JSON()),sa.Column("history",sa.JSON(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("lineage_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("asset_hash",sa.String(64),nullable=False),sa.Column("stage",sa.String(64),nullable=False),sa.Column("input_hash",sa.String(64),nullable=False),sa.Column("output_hash",sa.String(64)),sa.Column("code_version",sa.String(64),nullable=False),sa.Column("config_version",sa.String(64),nullable=False),sa.Column("success",sa.Boolean(),nullable=False),sa.Column("error_reason",sa.String(500)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("feature_flags",sa.Column("key",sa.String(64),primary_key=True),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("version",sa.Integer(),nullable=False),sa.Column("updated_by",sa.String(64),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("notifications",sa.Column("id",sa.String(36),primary_key=True),sa.Column("event_type",sa.String(64),nullable=False),sa.Column("message",sa.String(500),nullable=False),sa.Column("severity",sa.String(16),nullable=False),sa.Column("read",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("defects",sa.Column("id",sa.String(24),primary_key=True),sa.Column("title",sa.String(200),nullable=False),sa.Column("severity",sa.String(16),nullable=False),sa.Column("reproduction_steps",sa.Text(),nullable=False),sa.Column("expected_result",sa.Text(),nullable=False),sa.Column("actual_result",sa.Text(),nullable=False),sa.Column("affected_version",sa.String(64),nullable=False),sa.Column("assignee",sa.String(64)),sa.Column("status",sa.String(32),nullable=False),sa.Column("fixed_version",sa.String(64)),sa.Column("regression_test",sa.String(64)),sa.Column("capa_id",sa.String(24)))
    op.create_table("capas",sa.Column("id",sa.String(24),primary_key=True),sa.Column("defect_id",sa.String(24),nullable=False),sa.Column("root_cause",sa.Text(),nullable=False),sa.Column("corrective_action",sa.Text(),nullable=False),sa.Column("preventive_action",sa.Text(),nullable=False),sa.Column("effectiveness_check",sa.Text()),sa.Column("status",sa.String(32),nullable=False))

def downgrade():
    for name in ("capas","defects","notifications","feature_flags","lineage_events","label_tasks","pipeline_runs"):op.drop_table(name)
