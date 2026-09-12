"""Phase 30 QMS schema snapshot; application workflows remain WIP.
Revision ID: 0016_qms
Revises: 0015_integrations
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_qms'
down_revision = '0015_integrations'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('controlled_documents',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('document_number', sa.String(64), nullable=False, primary_key=False),
        sa.Column('document_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('title', sa.String(200), nullable=False, primary_key=False),
        sa.Column('current_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('status', sa.String(32), nullable=False, primary_key=False),
        sa.Column('owner_role', sa.String(32), nullable=False, primary_key=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True, primary_key=False),
        sa.Column('supersedes_document_id', sa.String(36), nullable=True, primary_key=False),
        sa.Column('retention_class', sa.String(32), nullable=False, primary_key=False),
        sa.Column('created_by', sa.String(64), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_controlled_documents_document_number', 'controlled_documents', ['document_number'], unique=True)
    op.create_index('ix_controlled_documents_status', 'controlled_documents', ['status'], unique=False)
    op.create_table('controlled_document_versions',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('document_id', sa.String(36), nullable=False, primary_key=False),
        sa.Column('version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('content', sa.Text(), nullable=False, primary_key=False),
        sa.Column('content_sha256', sa.String(64), nullable=False, primary_key=False),
        sa.Column('change_summary', sa.Text(), nullable=False, primary_key=False),
        sa.Column('source_references', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('status', sa.String(32), nullable=False, primary_key=False),
        sa.Column('created_by', sa.String(64), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('document_id', 'version'),
    )
    op.create_index('ix_controlled_document_versions_document_id', 'controlled_document_versions', ['document_id'], unique=False)
    op.create_table('document_reviews',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('document_version_id', sa.String(36), nullable=False, primary_key=False),
        sa.Column('reviewer_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('reviewer_role', sa.String(32), nullable=False, primary_key=False),
        sa.Column('decision', sa.String(32), nullable=False, primary_key=False),
        sa.Column('comment', sa.Text(), nullable=False, primary_key=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_document_reviews_document_version_id', 'document_reviews', ['document_version_id'], unique=False)
    op.create_table('electronic_approvals',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('target_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('target_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('target_version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('signer_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('signer_role', sa.String(32), nullable=False, primary_key=False),
        sa.Column('meaning', sa.String(32), nullable=False, primary_key=False),
        sa.Column('reason', sa.Text(), nullable=False, primary_key=False),
        sa.Column('content_sha256', sa.String(64), nullable=False, primary_key=False),
        sa.Column('request_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('authentication_method', sa.String(32), nullable=False, primary_key=False),
        sa.Column('reauthentication_status', sa.String(64), nullable=False, primary_key=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column('signature_status', sa.String(32), nullable=False, primary_key=False),
        sa.Column('previous_approval_id', sa.String(36), nullable=True, primary_key=False),
        sa.UniqueConstraint('request_id'),
    )
    op.create_index('ix_electronic_approvals_target_id', 'electronic_approvals', ['target_id'], unique=False)
    op.create_table('traceability_links',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('source_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('source_id', sa.String(100), nullable=False, primary_key=False),
        sa.Column('relationship', sa.String(64), nullable=False, primary_key=False),
        sa.Column('target_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('target_id', sa.String(100), nullable=False, primary_key=False),
        sa.Column('version', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('evidence', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_by', sa.String(64), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('source_type', 'source_id', 'relationship', 'target_type', 'target_id', 'version'),
    )
    op.create_index('ix_traceability_links_target_id', 'traceability_links', ['target_id'], unique=False)
    op.create_index('ix_traceability_links_source_id', 'traceability_links', ['source_id'], unique=False)
    op.create_index('ix_traceability_links_source_type', 'traceability_links', ['source_type'], unique=False)
    op.create_index('ix_traceability_links_target_type', 'traceability_links', ['target_type'], unique=False)
    op.create_table('change_requests',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('change_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('title', sa.String(200), nullable=False, primary_key=False),
        sa.Column('description', sa.Text(), nullable=False, primary_key=False),
        sa.Column('reason', sa.Text(), nullable=False, primary_key=False),
        sa.Column('requested_by', sa.String(64), nullable=False, primary_key=False),
        sa.Column('affected_components', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('affected_requirements', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('affected_risks', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('affected_tests', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('affected_models', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('affected_datasets', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('affected_integrations', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('impact_summary', sa.Text(), nullable=False, primary_key=False),
        sa.Column('status', sa.String(32), nullable=False, primary_key=False),
        sa.Column('implementation_version', sa.String(64), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_change_requests_change_id', 'change_requests', ['change_id'], unique=True)
    op.create_index('ix_change_requests_status', 'change_requests', ['status'], unique=False)
    op.create_table('impact_assessments',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('change_request_id', sa.String(36), nullable=False, primary_key=False),
        sa.Column('assessment_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('impact_level', sa.String(16), nullable=False, primary_key=False),
        sa.Column('affected_items', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('regression_scope', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('new_risks', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('regulatory_impact', sa.Text(), nullable=False, primary_key=False),
        sa.Column('cybersecurity_impact', sa.Text(), nullable=False, primary_key=False),
        sa.Column('privacy_impact', sa.Text(), nullable=False, primary_key=False),
        sa.Column('interoperability_impact', sa.Text(), nullable=False, primary_key=False),
        sa.Column('assessed_by', sa.String(64), nullable=False, primary_key=False),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_impact_assessments_change_request_id', 'impact_assessments', ['change_request_id'], unique=False)
    op.create_table('audit_evidence',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('evidence_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('evidence_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('related_type', sa.String(64), nullable=False, primary_key=False),
        sa.Column('related_id', sa.String(64), nullable=False, primary_key=False),
        sa.Column('filename', sa.String(200), nullable=False, primary_key=False),
        sa.Column('sha256', sa.String(64), nullable=False, primary_key=False),
        sa.Column('storage_status', sa.String(32), nullable=False, primary_key=False),
        sa.Column('generated_by', sa.String(64), nullable=False, primary_key=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('evidence_id'),
    )
    op.create_index('ix_audit_evidence_related_id', 'audit_evidence', ['related_id'], unique=False)
    op.create_table('audit_chain_entries',
        sa.Column('sequence', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.String(36), nullable=False, primary_key=False),
        sa.Column('previous_hash', sa.String(64), nullable=False, primary_key=False),
        sa.Column('event_hash', sa.String(64), nullable=False, primary_key=False),
        sa.Column('payload_hash', sa.String(64), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_index('ix_audit_chain_entries_event_id', 'audit_chain_entries', ['event_id'], unique=True)
    op.add_column('test_requirements', sa.Column('qms_data', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('ai_risks', sa.Column('qms_data', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('operational_capas', sa.Column('qms_data', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('defect_records', sa.Column('qms_data', sa.JSON(), nullable=False, server_default='{}'))

def downgrade():
    with op.batch_alter_table('defect_records') as batch:
        batch.drop_column('qms_data')
    with op.batch_alter_table('test_requirements') as batch:
        batch.drop_column('qms_data')
    with op.batch_alter_table('ai_risks') as batch:
        batch.drop_column('qms_data')
    with op.batch_alter_table('operational_capas') as batch:
        batch.drop_column('qms_data')
    op.drop_table('audit_chain_entries')
    op.drop_table('audit_evidence')
    op.drop_table('impact_assessments')
    op.drop_table('change_requests')
    op.drop_table('traceability_links')
    op.drop_table('electronic_approvals')
    op.drop_table('document_reviews')
    op.drop_table('controlled_document_versions')
    op.drop_table('controlled_documents')
