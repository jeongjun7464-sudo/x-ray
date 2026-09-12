"""Phase 29 integration persistence; no credentials or raw UIDs."""
from alembic import op
import sqlalchemy as sa
revision = "0015_integrations"
down_revision = "0014_modelops"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("institution_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(64), nullable=False),
        sa.Column("connection_type", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("base_url_masked", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("tls_verification", sa.Boolean(), nullable=False),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("external_transfer_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(64), nullable=False),
        sa.Column("transfer_type", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("destination", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("response_status", sa.Integer()),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("failure_message", sa.String(200)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("institution_id", "idempotency_key", name="uq_transfer_institution_key"))
    op.create_table("external_transfer_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transfer_job_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("dicom_uid_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(64), nullable=False),
        sa.Column("study_uid_hash", sa.String(64), nullable=False),
        sa.Column("series_uid_hash", sa.String(64), nullable=False),
        sa.Column("sop_uid_hash", sa.String(64), nullable=False),
        sa.Column("mapping_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institution_id", "sop_uid_hash", name="uq_institution_sop_hash"))
    op.create_table("fhir_export_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(64), nullable=False),
        sa.Column("analysis_id", sa.String(36), nullable=False),
        sa.Column("bundle_type", sa.String(32), nullable=False),
        sa.Column("bundle_sha256", sa.String(64), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False),
        sa.Column("transmission_status", sa.String(32), nullable=False),
        sa.Column("destination", sa.String(24), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for table in ("institution_connections", "external_transfer_jobs", "dicom_uid_mappings", "fhir_export_records"):
        op.create_index("ix_" + table + "_institution_id", table, ["institution_id"])
    op.create_index("ix_external_transfer_events_transfer_job_id", "external_transfer_events", ["transfer_job_id"])

def downgrade():
    for table in ("fhir_export_records", "dicom_uid_mappings", "external_transfer_events", "external_transfer_jobs", "institution_connections"):
        op.drop_table(table)
