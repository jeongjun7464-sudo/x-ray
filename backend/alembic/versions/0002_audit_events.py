"""Add append-only audit events."""
from alembic import op
import sqlalchemy as sa

revision = "0002_audit_events"
down_revision = "0001_initial"


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64)),
        sa.Column("before_value", sa.JSON()),
        sa.Column("after_value", sa.JSON()),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade():
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
