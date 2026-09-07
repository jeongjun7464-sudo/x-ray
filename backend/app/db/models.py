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

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    final_route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class LabelTask(Base):
    __tablename__ = "label_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_hash: Mapped[str] = mapped_column(String(64), index=True)
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="NOT_REVIEWED")
    first_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    second_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_label: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class LineageEvent(Base):
    __tablename__ = "lineage_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_hash: Mapped[str] = mapped_column(String(64), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_version: Mapped[str] = mapped_column(String(64))
    config_version: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    error_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Defect(Base):
    __tablename__ = "defects"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(16))
    reproduction_steps: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)
    actual_result: Mapped[str] = mapped_column(Text)
    affected_version: Mapped[str] = mapped_column(String(64))
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    fixed_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    regression_test: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capa_id: Mapped[str | None] = mapped_column(String(24), nullable=True)

class Capa(Base):
    __tablename__ = "capas"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    defect_id: Mapped[str] = mapped_column(String(24), index=True)
    root_cause: Mapped[str] = mapped_column(Text)
    corrective_action: Mapped[str] = mapped_column(Text)
    preventive_action: Mapped[str] = mapped_column(Text)
    effectiveness_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ANALYSIS")

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    anonymous_user_id: Mapped[str] = mapped_column(String(64), index=True)
    user_role: Mapped[str] = mapped_column(String(32))
    masked_query: Mapped[str] = mapped_column(Text)
    selected_agent: Mapped[str] = mapped_column(String(64))
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text)
    safety_result: Mapped[dict] = mapped_column(JSON, default=dict)
    trace: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(32), default="dummy")
    model: Mapped[str] = mapped_column(String(64), default="deterministic-agent-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AgentFeedback(Base):
    __tablename__ = "agent_feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    rating: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    agent_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AgentActionProposal(Base):
    __tablename__ = "agent_action_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(64))
    required_role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="AWAITING_CONFIRMATION")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserConsent(Base):
    __tablename__ = "user_consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    anonymous_user_id: Mapped[str] = mapped_column(String(64), index=True)
    consent_version: Mapped[str] = mapped_column(String(32), index=True)
    accepted_items: Mapped[list] = mapped_column(JSON, default=list)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class LatencyRecord(Base):
    __tablename__ = "latency_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id: Mapped[str] = mapped_column(String(36), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    device: Mapped[str] = mapped_column(String(16), default="CPU")
    stages_ms: Mapped[dict] = mapped_column(JSON, default=dict)
    total_ms: Mapped[float] = mapped_column(Float)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MisclassificationReport(Base):
    __tablename__ = "misclassification_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_id: Mapped[str] = mapped_column(String(36), index=True)
    report_type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(32), default="REVIEW_REQUIRED")
    linked_work_item: Mapped[str] = mapped_column(String(64))
    capa_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AIRisk(Base):
    __tablename__ = "ai_risks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    control: Mapped[str] = mapped_column(Text)
    verification_test: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str] = mapped_column(String(64))
    residual_risk: Mapped[str] = mapped_column(String(16))

class XrayAnalysis(Base):
    __tablename__="xray_analyses"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    anonymous_hash: Mapped[str]=mapped_column(String(64),index=True)
    modality: Mapped[str]=mapped_column(String(16),default="UNKNOWN")
    is_dicom: Mapped[bool]=mapped_column(Boolean)
    quality: Mapped[dict]=mapped_column(JSON)
    region_result: Mapped[dict]=mapped_column(JSON)
    screening_status: Mapped[str]=mapped_column(String(40),index=True)
    uncertainty: Mapped[dict]=mapped_column(JSON)
    routing: Mapped[dict]=mapped_column(JSON)
    model_info: Mapped[dict]=mapped_column(JSON)
    reviewed: Mapped[bool]=mapped_column(Boolean,default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class FindingPredictionRecord(Base):
    __tablename__="finding_predictions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    analysis_id: Mapped[str]=mapped_column(String(36),index=True)
    code: Mapped[str]=mapped_column(String(64));display_name: Mapped[str]=mapped_column(String(100))
    probability: Mapped[float]=mapped_column(Float);threshold: Mapped[float]=mapped_column(Float);positive: Mapped[bool]=mapped_column(Boolean)

class ExplanationArtifact(Base):
    __tablename__="explanation_artifacts"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    analysis_id: Mapped[str]=mapped_column(String(36),index=True);artifact_type: Mapped[str]=mapped_column(String(32));storage_uri: Mapped[str|None]=mapped_column(String(500),nullable=True);available: Mapped[bool]=mapped_column(Boolean,default=False)

class ClinicalReview(Base):
    __tablename__="clinical_reviews"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    analysis_id: Mapped[str]=mapped_column(String(36),index=True);reviewer_role: Mapped[str]=mapped_column(String(32));final_region: Mapped[str]=mapped_column(String(32));final_findings: Mapped[list]=mapped_column(JSON);comment: Mapped[str]=mapped_column(Text,default="");before_value: Mapped[dict]=mapped_column(JSON);after_value: Mapped[dict]=mapped_column(JSON);audit_event_id: Mapped[str|None]=mapped_column(String(36),nullable=True);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ModelRegistry(Base):
    __tablename__="model_registry"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));model_name: Mapped[str]=mapped_column(String(100),index=True);model_version: Mapped[str]=mapped_column(String(64),index=True);checkpoint_hash: Mapped[str|None]=mapped_column(String(64),nullable=True);dummy_mode: Mapped[bool]=mapped_column(Boolean);approval_status: Mapped[str]=mapped_column(String(32),default="DEMO_ONLY")

class LongitudinalComparison(Base):
    __tablename__="longitudinal_comparisons"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    prior_analysis_id: Mapped[str]=mapped_column(String(36),index=True)
    current_analysis_id: Mapped[str]=mapped_column(String(36),index=True)
    compatibility: Mapped[dict]=mapped_column(JSON,default=dict)
    changes: Mapped[dict]=mapped_column(JSON,default=dict)
    review_status: Mapped[str]=mapped_column(String(32),default="REVIEW_REQUIRED")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ActiveLearningCandidate(Base):
    __tablename__="active_learning_candidates"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    analysis_id: Mapped[str]=mapped_column(String(36),index=True)
    anonymous_hash: Mapped[str]=mapped_column(String(64),index=True)
    original_labels: Mapped[dict]=mapped_column(JSON)
    corrected_labels: Mapped[dict]=mapped_column(JSON)
    model_version: Mapped[str]=mapped_column(String(64))
    approved_for_export: Mapped[bool]=mapped_column(Boolean,default=False)
    auto_training_enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class DatasetVersion(Base):
    __tablename__="dataset_versions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    name: Mapped[str]=mapped_column(String(100),index=True)
    version: Mapped[str]=mapped_column(String(32),index=True)
    status: Mapped[str]=mapped_column(String(32),default="DRAFT")
    manifest: Mapped[list]=mapped_column(JSON,default=list)
    duplicate_count: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ModelDeployment(Base):
    __tablename__="model_deployments"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    model_version: Mapped[str]=mapped_column(String(64),index=True)
    checkpoint_sha256: Mapped[str]=mapped_column(String(64))
    dataset_version: Mapped[str]=mapped_column(String(64))
    deployment_status: Mapped[str]=mapped_column(String(32),default="DEMO_ONLY")
    performance_status: Mapped[str]=mapped_column(String(32),default="NOT_MEASURED")
    drift_status: Mapped[str]=mapped_column(String(32),default="INSUFFICIENT_DATA")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class StudyAnalysis(Base):
    __tablename__="study_analyses"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    study_id: Mapped[str]=mapped_column(String(36),index=True)
    instance_results: Mapped[list]=mapped_column(JSON,default=list)
    aggregate_result: Mapped[dict]=mapped_column(JSON,default=dict)
    clinical_context: Mapped[dict]=mapped_column(JSON,default=dict)
    clinical_context_effect: Mapped[dict]=mapped_column(JSON,default=dict)
    status: Mapped[str]=mapped_column(String(32),index=True,default="REVIEW_REQUIRED")
    priority_reasons: Mapped[list]=mapped_column(JSON,default=list)
    priority_rule_version: Mapped[str]=mapped_column(String(32),default="1.0")
    reviewed: Mapped[bool]=mapped_column(Boolean,default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ReviewPriorityRule(Base):
    __tablename__="review_priority_rules"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    version: Mapped[str]=mapped_column(String(32),unique=True,index=True)
    thresholds: Mapped[dict]=mapped_column(JSON,default=dict)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    changed_by: Mapped[str]=mapped_column(String(64),default="system")
    change_reason: Mapped[str]=mapped_column(String(500),default="initial rule")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ModelRelease(Base):
    __tablename__="model_releases"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    name: Mapped[str]=mapped_column(String(100),index=True)
    version: Mapped[str]=mapped_column(String(64),index=True)
    model_sha256: Mapped[str]=mapped_column(String(64),unique=True)
    training_dataset_version: Mapped[str]=mapped_column(String(64))
    test_dataset_version: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(32),default="REGISTERED",index=True)
    automated_tests: Mapped[dict]=mapped_column(JSON,default=dict)
    comparison_result: Mapped[dict]=mapped_column(JSON,default=dict)
    approver: Mapped[str|None]=mapped_column(String(64),nullable=True)
    approval_reason: Mapped[str|None]=mapped_column(String(500),nullable=True)
    rollback_model_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class OperationalCapa(Base):
    __tablename__="operational_capas"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    error_type: Mapped[str]=mapped_column(String(64),index=True)
    occurrence_count: Mapped[int]=mapped_column(Integer,default=1)
    model_version: Mapped[str]=mapped_column(String(64),default="UNKNOWN")
    dataset_version: Mapped[str]=mapped_column(String(64),default="UNKNOWN")
    analysis_ids: Mapped[list]=mapped_column(JSON,default=list)
    root_cause: Mapped[str]=mapped_column(Text,default="")
    corrective_action: Mapped[str]=mapped_column(Text,default="")
    preventive_action: Mapped[str]=mapped_column(Text,default="")
    owner: Mapped[str]=mapped_column(String(64),default="UNASSIGNED")
    due_date: Mapped[str|None]=mapped_column(String(16),nullable=True)
    effectiveness_check: Mapped[str]=mapped_column(Text,default="")
    status: Mapped[str]=mapped_column(String(32),default="CANDIDATE")
    approved_by: Mapped[str|None]=mapped_column(String(64),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class ErrorOccurrence(Base):
    __tablename__="error_occurrences"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    error_type: Mapped[str]=mapped_column(String(64),index=True)
    analysis_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    model_version: Mapped[str]=mapped_column(String(64),default="UNKNOWN")
    dataset_version: Mapped[str]=mapped_column(String(64),default="UNKNOWN")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AnalysisProvenance(Base):
    __tablename__="analysis_provenance"
    analysis_id: Mapped[str]=mapped_column(String(36),primary_key=True)
    input_sha256: Mapped[str]=mapped_column(String(64),index=True)
    manifest: Mapped[dict]=mapped_column(JSON)
    raw_input_retained: Mapped[bool]=mapped_column(Boolean,default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class TestRequirement(Base):
    __tablename__="test_requirements"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));requirement_id: Mapped[str]=mapped_column(String(64),unique=True,index=True);risk_ids: Mapped[list]=mapped_column(JSON,default=list);title: Mapped[str]=mapped_column(String(200))
class TestScenario(Base):
    __tablename__="test_scenarios"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));test_id: Mapped[str]=mapped_column(String(64),unique=True,index=True);requirement_id: Mapped[str]=mapped_column(String(64),index=True);risk_ids: Mapped[list]=mapped_column(JSON,default=list);scenario_type: Mapped[str]=mapped_column(String(32));preconditions: Mapped[str]=mapped_column(Text);input_data: Mapped[dict]=mapped_column(JSON);steps: Mapped[list]=mapped_column(JSON);expected_result: Mapped[str]=mapped_column(Text)
class TestExecution(Base):
    __tablename__="test_executions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));scenario_id: Mapped[str]=mapped_column(String(36),index=True);actual_result: Mapped[str]=mapped_column(Text);status: Mapped[str]=mapped_column(String(16));tester: Mapped[str]=mapped_column(String(64));retest_of: Mapped[str|None]=mapped_column(String(36),nullable=True);executed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class TestEvidence(Base):
    __tablename__="test_evidence"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));execution_id: Mapped[str]=mapped_column(String(36),index=True);filename: Mapped[str]=mapped_column(String(200));sha256: Mapped[str]=mapped_column(String(64));storage_status: Mapped[str]=mapped_column(String(32),default="METADATA_ONLY")
class DefectRecord(Base):
    __tablename__="defect_records"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));execution_id: Mapped[str]=mapped_column(String(36),index=True);summary: Mapped[str]=mapped_column(String(300));status: Mapped[str]=mapped_column(String(32),default="OPEN")

class AnnotationRecord(Base):
    __tablename__="annotation_records"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));anonymous_image_hash: Mapped[str]=mapped_column(String(64),index=True);first_review: Mapped[dict]=mapped_column(JSON);second_review: Mapped[dict|None]=mapped_column(JSON,nullable=True);adjudication: Mapped[dict|None]=mapped_column(JSON,nullable=True);final_label: Mapped[dict|None]=mapped_column(JSON,nullable=True);status: Mapped[str]=mapped_column(String(32),default="FIRST_REVIEWED");history: Mapped[list]=mapped_column(JSON,default=list);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class RecoveryJob(Base):
    __tablename__="recovery_jobs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));idempotency_key: Mapped[str]=mapped_column(String(100),unique=True,index=True);analysis_id: Mapped[str|None]=mapped_column(String(36),nullable=True);status: Mapped[str]=mapped_column(String(32),default="QUEUED");attempts: Mapped[int]=mapped_column(Integer,default=0);max_attempts: Mapped[int]=mapped_column(Integer,default=3);next_retry_seconds: Mapped[int]=mapped_column(Integer,default=0);failure_reason: Mapped[str|None]=mapped_column(String(500),nullable=True);model_version: Mapped[str]=mapped_column(String(64),default="UNKNOWN");created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AuditPackage(Base):
    __tablename__="audit_packages"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));created_by_role: Mapped[str]=mapped_column(String(32));manifest: Mapped[dict]=mapped_column(JSON);payload_base64: Mapped[str]=mapped_column(Text);package_sha256: Mapped[str]=mapped_column(String(64));status: Mapped[str]=mapped_column(String(32),default="READY");created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class SecurityEvent(Base):
    __tablename__="security_events"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));event_type: Mapped[str]=mapped_column(String(64),index=True);request_id: Mapped[str]=mapped_column(String(64),index=True);details: Mapped[dict]=mapped_column(JSON,default=dict);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class KnowledgeDocument(Base):
    __tablename__="knowledge_documents";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));document_id: Mapped[str]=mapped_column(String(80),unique=True,index=True);title: Mapped[str]=mapped_column(String(200));document_type: Mapped[str]=mapped_column(String(40));institution_id: Mapped[str]=mapped_column(String(64),index=True);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class KnowledgeDocumentVersion(Base):
    __tablename__="knowledge_document_versions";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));document_id: Mapped[str]=mapped_column(String(80),index=True);version: Mapped[str]=mapped_column(String(32),index=True);approval_status: Mapped[str]=mapped_column(String(32),index=True);effective_date: Mapped[str]=mapped_column(String(16));expires_at: Mapped[str|None]=mapped_column(String(32),nullable=True);allowed_roles: Mapped[list]=mapped_column(JSON,default=list);content_hash: Mapped[str]=mapped_column(String(64),index=True);search_enabled: Mapped[bool]=mapped_column(Boolean,default=True);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class KnowledgeChunk(Base):
    __tablename__="knowledge_chunks";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));document_id: Mapped[str]=mapped_column(String(80),index=True);version: Mapped[str]=mapped_column(String(32));chunk_id: Mapped[str]=mapped_column(String(140),unique=True,index=True);qdrant_point_id: Mapped[str|None]=mapped_column(String(64),nullable=True);content_hash: Mapped[str]=mapped_column(String(64),index=True);embedding_model: Mapped[str]=mapped_column(String(120));section: Mapped[str]=mapped_column(String(160));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class KnowledgeIndexRun(Base):
    __tablename__="knowledge_index_runs";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));status: Mapped[str]=mapped_column(String(32));indexed_count: Mapped[int]=mapped_column(Integer,default=0);skipped_count: Mapped[int]=mapped_column(Integer,default=0);failed_documents: Mapped[list]=mapped_column(JSON,default=list);retrieval_mode: Mapped[str]=mapped_column(String(32));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AgentConversation(Base):
    __tablename__="agent_conversations";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));anonymous_user_id: Mapped[str]=mapped_column(String(64));institution_id: Mapped[str]=mapped_column(String(64));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AgentMessage(Base):
    __tablename__="agent_messages";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));conversation_id: Mapped[str]=mapped_column(String(36),index=True);role: Mapped[str]=mapped_column(String(16));masked_content: Mapped[str]=mapped_column(Text);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AgentRetrievalEvent(Base):
    __tablename__="agent_retrieval_events";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));run_id: Mapped[str]=mapped_column(String(36),index=True);document_id: Mapped[str]=mapped_column(String(80));chunk_id: Mapped[str]=mapped_column(String(140));bm25_rank: Mapped[int|None]=mapped_column(Integer,nullable=True);vector_rank: Mapped[int|None]=mapped_column(Integer,nullable=True);rrf_score: Mapped[float]=mapped_column(Float);selected: Mapped[bool]=mapped_column(Boolean);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class LLMInferenceEvent(Base):
    __tablename__="llm_inference_events";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));run_id: Mapped[str]=mapped_column(String(36),index=True);provider: Mapped[str]=mapped_column(String(32));model_name: Mapped[str]=mapped_column(String(120));model_version: Mapped[str]=mapped_column(String(120));prompt_template_version: Mapped[str]=mapped_column(String(32));prompt_tokens: Mapped[int]=mapped_column(Integer);completion_tokens: Mapped[int]=mapped_column(Integer);latency_ms: Mapped[float]=mapped_column(Float);finish_reason: Mapped[str]=mapped_column(String(32));dummy_mode: Mapped[bool]=mapped_column(Boolean);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ConsistencyValidationRun(Base):
    __tablename__="consistency_validation_runs";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));scope: Mapped[str]=mapped_column(String(40),index=True);target_type: Mapped[str]=mapped_column(String(40));target_id: Mapped[str|None]=mapped_column(String(80),nullable=True,index=True);rule_engine_version: Mapped[str]=mapped_column(String(32));summary: Mapped[dict]=mapped_column(JSON);high_risk_block: Mapped[bool]=mapped_column(Boolean);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ConsistencyFindingRecord(Base):
    __tablename__="consistency_findings";id: Mapped[str]=mapped_column(String(36),primary_key=True);validation_run_id: Mapped[str]=mapped_column(String(36),index=True);rule_id: Mapped[str]=mapped_column(String(32),index=True);rule_version: Mapped[str]=mapped_column(String(16));category: Mapped[str]=mapped_column(String(40),index=True);target_resource: Mapped[str]=mapped_column(String(160));expected: Mapped[dict]=mapped_column(JSON);actual: Mapped[dict]=mapped_column(JSON);status: Mapped[str]=mapped_column(String(32),index=True);severity: Mapped[str]=mapped_column(String(16),index=True);message: Mapped[str]=mapped_column(Text);automatic_action: Mapped[str]=mapped_column(String(64));assigned_role: Mapped[str|None]=mapped_column(String(32),nullable=True,index=True);resolved: Mapped[bool]=mapped_column(Boolean,default=False,index=True);validation_type: Mapped[str]=mapped_column(String(32));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc));updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ConsistencyEvidence(Base):
    __tablename__="consistency_evidence";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));finding_id: Mapped[str]=mapped_column(String(36),index=True);source_type: Mapped[str]=mapped_column(String(40));source_id: Mapped[str]=mapped_column(String(120));field: Mapped[str]=mapped_column(String(120));value_hash: Mapped[str|None]=mapped_column(String(64),nullable=True)
class ConsistencyRuleVersion(Base):
    __tablename__="consistency_rule_versions";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));rule_id: Mapped[str]=mapped_column(String(32),index=True);version: Mapped[str]=mapped_column(String(16));definition_hash: Mapped[str]=mapped_column(String(64));active: Mapped[bool]=mapped_column(Boolean,default=True);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ConsistencyResolution(Base):
    __tablename__="consistency_resolutions";id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));finding_id: Mapped[str]=mapped_column(String(36),index=True);assigned_role: Mapped[str]=mapped_column(String(32));comment: Mapped[str]=mapped_column(Text);resolution_evidence: Mapped[dict]=mapped_column(JSON);change_reason: Mapped[str]=mapped_column(String(500));resolved: Mapped[bool]=mapped_column(Boolean);resolved_by: Mapped[str]=mapped_column(String(64));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
