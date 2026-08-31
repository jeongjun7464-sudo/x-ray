"""medical agent execution, feedback and confirmation tables

Revision ID: 0005_medical_agent
Revises: 0004_ai_validation
"""
from alembic import op
import sqlalchemy as sa
revision="0005_medical_agent";down_revision="0004_ai_validation";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("agent_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("request_id",sa.String(64),nullable=False),sa.Column("anonymous_user_id",sa.String(64),nullable=False),sa.Column("user_role",sa.String(32),nullable=False),sa.Column("masked_query",sa.Text(),nullable=False),sa.Column("selected_agent",sa.String(64),nullable=False),sa.Column("tool_calls",sa.JSON(),nullable=False),sa.Column("document_ids",sa.JSON(),nullable=False),sa.Column("answer",sa.Text(),nullable=False),sa.Column("safety_result",sa.JSON(),nullable=False),sa.Column("trace",sa.JSON(),nullable=False),sa.Column("provider",sa.String(32),nullable=False),sa.Column("model",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("agent_feedback",sa.Column("id",sa.String(36),primary_key=True),sa.Column("run_id",sa.String(36),nullable=False),sa.Column("rating",sa.String(32),nullable=False),sa.Column("comment",sa.String(1000)),sa.Column("agent_version",sa.String(64),nullable=False),sa.Column("prompt_version",sa.String(32),nullable=False),sa.Column("model_version",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("agent_action_proposals",sa.Column("id",sa.String(36),primary_key=True),sa.Column("action",sa.String(64),nullable=False),sa.Column("arguments",sa.JSON(),nullable=False),sa.Column("requested_by",sa.String(64),nullable=False),sa.Column("required_role",sa.String(32),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
def downgrade():
    op.drop_table("agent_action_proposals");op.drop_table("agent_feedback");op.drop_table("agent_runs")
