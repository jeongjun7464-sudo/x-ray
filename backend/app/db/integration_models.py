"""Persistent integration records. Credentials and raw UIDs are never columns."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

def now(): return datetime.now(timezone.utc)
class InstitutionConnection(Base):
    __tablename__ = "institution_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(64), index=True)
    connection_type: Mapped[str] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(24))
    base_url_masked: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="NOT_CONFIGURED")
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tls_verification: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ExternalTransferJob(Base):
    __tablename__ = "external_transfer_jobs"
    __table_args__ = (UniqueConstraint("institution_id", "idempotency_key", name="uq_transfer_institution_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(64), index=True)
    transfer_type: Mapped[str] = mapped_column(String(32))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(64))
    destination: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), default="AWAITING_CONFIRMATION")
    idempotency_key: Mapped[str] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_status: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ExternalTransferEvent(Base):
    __tablename__ = "external_transfer_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transfer_job_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    request_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class DicomUidMapping(Base):
    __tablename__ = "dicom_uid_mappings"
    __table_args__ = (UniqueConstraint("institution_id", "sop_uid_hash", name="uq_institution_sop_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(64), index=True)
    study_uid_hash: Mapped[str] = mapped_column(String(64))
    series_uid_hash: Mapped[str] = mapped_column(String(64))
    sop_uid_hash: Mapped[str] = mapped_column(String(64))
    mapping_status: Mapped[str] = mapped_column(String(32), default="HASH_ONLY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class FhirExportRecord(Base):
    __tablename__ = "fhir_export_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_id: Mapped[str] = mapped_column(String(36))
    bundle_type: Mapped[str] = mapped_column(String(32))
    bundle_sha256: Mapped[str] = mapped_column(String(64))
    validation_status: Mapped[str] = mapped_column(String(32))
    transmission_status: Mapped[str] = mapped_column(String(32))
    destination: Mapped[str] = mapped_column(String(24))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
