"""Controlled QMS records; legacy requirements, risks, CAPA and packages are reused."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid.uuid4())

class ControlledDocument(Base):
    __tablename__ = 'controlled_documents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    document_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default='DRAFT', index=True)
    owner_role: Mapped[str] = mapped_column(String(32))
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    retention_class: Mapped[str] = mapped_column(String(32), default='QA_REVIEW_REQUIRED')
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class ControlledDocumentVersion(Base):
    __tablename__ = 'controlled_document_versions'
    __table_args__ = (UniqueConstraint('document_id', 'version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    change_summary: Mapped[str] = mapped_column(Text)
    source_references: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default='DRAFT')
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DocumentReview(Base):
    __tablename__ = 'document_reviews'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(String(36), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(64))
    reviewer_role: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ElectronicApproval(Base):
    __tablename__ = 'electronic_approvals'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    target_version: Mapped[int] = mapped_column(Integer)
    signer_id: Mapped[str] = mapped_column(String(64))
    signer_role: Mapped[str] = mapped_column(String(32))
    meaning: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(64), unique=True)
    authentication_method: Mapped[str] = mapped_column(String(32))
    reauthentication_status: Mapped[str] = mapped_column(String(64))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    signature_status: Mapped[str] = mapped_column(String(32))
    previous_approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

class TraceabilityLink(Base):
    __tablename__ = 'traceability_links'
    __table_args__ = (UniqueConstraint('source_type', 'source_id', 'relationship', 'target_type', 'target_id', 'version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(100), index=True)
    relationship: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ChangeRequest(Base):
    __tablename__ = 'change_requests'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    change_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(64))
    affected_components: Mapped[list] = mapped_column(JSON, default=list)
    affected_requirements: Mapped[list] = mapped_column(JSON, default=list)
    affected_risks: Mapped[list] = mapped_column(JSON, default=list)
    affected_tests: Mapped[list] = mapped_column(JSON, default=list)
    affected_models: Mapped[list] = mapped_column(JSON, default=list)
    affected_datasets: Mapped[list] = mapped_column(JSON, default=list)
    affected_integrations: Mapped[list] = mapped_column(JSON, default=list)
    impact_summary: Mapped[str] = mapped_column(Text, default='HUMAN_INPUT_REQUIRED')
    status: Mapped[str] = mapped_column(String(32), default='PROPOSED', index=True)
    implementation_version: Mapped[str] = mapped_column(String(64), default='NOT_IMPLEMENTED')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class ImpactAssessment(Base):
    __tablename__ = 'impact_assessments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    change_request_id: Mapped[str] = mapped_column(String(36), index=True)
    assessment_type: Mapped[str] = mapped_column(String(64))
    impact_level: Mapped[str] = mapped_column(String(16))
    affected_items: Mapped[list] = mapped_column(JSON)
    regression_scope: Mapped[list] = mapped_column(JSON)
    new_risks: Mapped[list] = mapped_column(JSON)
    regulatory_impact: Mapped[str] = mapped_column(Text)
    cybersecurity_impact: Mapped[str] = mapped_column(Text)
    privacy_impact: Mapped[str] = mapped_column(Text)
    interoperability_impact: Mapped[str] = mapped_column(Text)
    assessed_by: Mapped[str] = mapped_column(String(64))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditEvidence(Base):
    __tablename__ = 'audit_evidence'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evidence_id: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_type: Mapped[str] = mapped_column(String(64))
    related_type: Mapped[str] = mapped_column(String(64))
    related_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    storage_status: Mapped[str] = mapped_column(String(32))
    generated_by: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditChainEntry(Base):
    __tablename__ = 'audit_chain_entries'
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

def immutable(*args): raise ValueError('APPEND_ONLY_RECORD')
for model in (ElectronicApproval, DocumentReview, AuditChainEntry, AuditEvidence, ControlledDocumentVersion):
    event.listen(model, 'before_update', immutable)
    event.listen(model, 'before_delete', immutable)
