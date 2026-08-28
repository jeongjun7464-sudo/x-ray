"""Initial prediction schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None


def upgrade():
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("file_hash", sa.String(64), nullable=False, index=True),
        sa.Column("file_format", sa.String(12), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("anatomical_region", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("top_predictions", sa.JSON(), nullable=False),
        sa.Column("laterality", sa.String(16), nullable=False),
        sa.Column("view_position", sa.String(16), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("review_reasons", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("dummy_mode", sa.Boolean(), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("corrected_region", sa.String(32)),
        sa.Column("review_comment", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("predictions")
