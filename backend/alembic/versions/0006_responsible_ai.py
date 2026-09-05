"""phase 23 responsible AI

Revision ID: 0006_responsible_ai
Revises: 0005_medical_agent
"""
from alembic import op
import sqlalchemy as sa

revision="0006_responsible_ai"
down_revision="0005_medical_agent"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("user_consents",sa.Column("id",sa.String(36),primary_key=True),sa.Column("anonymous_user_id",sa.String(64),nullable=False),sa.Column("consent_version",sa.String(32),nullable=False),sa.Column("accepted_items",sa.JSON(),nullable=False),sa.Column("accepted",sa.Boolean(),nullable=False),sa.Column("confirmed_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_user_consents_anonymous_user_id","user_consents",["anonymous_user_id"]);op.create_index("ix_user_consents_consent_version","user_consents",["consent_version"])
    op.create_table("latency_records",sa.Column("id",sa.String(36),primary_key=True),sa.Column("prediction_id",sa.String(36),nullable=False),sa.Column("model_version",sa.String(64),nullable=False),sa.Column("device",sa.String(16),nullable=False),sa.Column("stages_ms",sa.JSON(),nullable=False),sa.Column("total_ms",sa.Float(),nullable=False),sa.Column("timed_out",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_latency_records_prediction_id","latency_records",["prediction_id"]);op.create_index("ix_latency_records_model_version","latency_records",["model_version"])
    op.create_table("misclassification_reports",sa.Column("id",sa.String(36),primary_key=True),sa.Column("prediction_id",sa.String(36),nullable=False),sa.Column("report_type",sa.String(64),nullable=False),sa.Column("description",sa.String(1000),nullable=False),sa.Column("severity",sa.String(16),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("linked_work_item",sa.String(64),nullable=False),sa.Column("capa_candidate",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_misclassification_reports_prediction_id","misclassification_reports",["prediction_id"]);op.create_index("ix_misclassification_reports_report_type","misclassification_reports",["report_type"])
    op.create_table("ai_risks",sa.Column("id",sa.String(32),primary_key=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("control",sa.Text(),nullable=False),sa.Column("verification_test",sa.String(120),nullable=False),sa.Column("owner",sa.String(64),nullable=False),sa.Column("residual_risk",sa.String(16),nullable=False))

def downgrade():
    op.drop_table("ai_risks");op.drop_table("misclassification_reports");op.drop_table("latency_records");op.drop_table("user_consents")
