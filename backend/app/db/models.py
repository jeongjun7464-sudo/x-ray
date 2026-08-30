import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_format: Mapped[str] = mapped_column(String(12))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    anatomical_region: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    top_predictions: Mapped[list] = mapped_column(JSON)
    laterality: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    view_position: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reasons: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(64))
    dummy_mode: Mapped[bool] = mapped_column(Boolean)
    processing_time_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    corrected_region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String(64), default="anonymous")
    actor_role: Mapped[str] = mapped_column(String(32), default="USER")
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Study(Base):
    __tablename__ = "studies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    anonymous_accession: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    study_uid_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    study_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    region: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    protocol_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN_PROTOCOL")
    views: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class StudyInstance(Base):
    __tablename__ = "study_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    study_id: Mapped[str] = mapped_column(String(36), index=True)
    series_uid_hash: Mapped[str] = mapped_column(String(64), index=True)
    sop_uid_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    series_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instance_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_position: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    laterality: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    prediction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

class ProtocolDefinition(Base):
    __tablename__ = "protocol_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    region: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    required_views: Mapped[list] = mapped_column(JSON, default=list)
    optional_views: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")

class CodeMapping(Base):
    __tablename__ = "code_mappings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    internal_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    korean_name: Mapped[str] = mapped_column(String(64))
    english_name: Mapped[str] = mapped_column(String(64))
    snomed_ct: Mapped[str | None] = mapped_column(String(64), nullable=True)
    radlex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dicom_body_part: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")

class RoutingRule(Base):
    __tablename__ = "routing_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    destination: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class IntegrationEvent(Base):
    __tablename__ = "integration_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
