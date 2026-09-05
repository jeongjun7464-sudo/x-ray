from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class TopPrediction(BaseModel):
    class_: str = Field(alias="class", serialization_alias="class")
    display_name: str
    confidence: float = Field(ge=0, le=1)
    model_config = ConfigDict(populate_by_name=True)
class PredictionOut(BaseModel):
    prediction_id: str
    anatomical_region: str
    display_name: str
    confidence: float
    top_predictions: list[TopPrediction]
    laterality: str
    view_position: str
    review_required: bool
    review_reasons: list[str]
    model_version: str
    dummy_mode: bool
    processing_time_ms: int
    created_at: datetime | None = None
    preview_data_url: str | None = None
    explanation_available: bool = False
    quality_status: str | None = None
    quality_score: float | None = None
    quality_reasons: list[str] = []
    distribution_status: str | None = None
    metadata_status: str | None = None
    metadata_warnings: list[str] = []
    routing_target: str | None = None
    priority: str | None = None
    pipeline_run_id: str | None = None
    pipeline_stages: list[dict] = []
class ReviewUpdate(BaseModel):
    corrected_region: str
    comment: str = Field(default="", max_length=1000)
class ValidationOut(BaseModel):
    valid: bool
    file_format: str
    width: int
    height: int
    message: str

class ProtocolIn(BaseModel):
    region: str
    required_views: list[str]
    optional_views: list[str] = []
    active: bool = True
    version: str = "1.0"

class CodeMappingIn(BaseModel):
    internal_code: str
    korean_name: str
    english_name: str
    snomed_ct: str | None = None
    radlex: str | None = None
    dicom_body_part: str | None = None
    active: bool = True
    version: str = "1.0"

class RoutingRuleIn(BaseModel):
    name: str
    priority: int = Field(ge=1, le=10000)
    conditions: dict
    destination: str
    active: bool = True
    version: str = "1.0"

class StudyTagsIn(BaseModel):
    tags: list[dict]

class AgentChatIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None

class AgentFeedbackIn(BaseModel):
    rating: str
    comment: str = Field(default="", max_length=1000)

class AgentActionIn(BaseModel):
    action: str
    arguments: dict = {}

class ConsentIn(BaseModel):
    anonymous_user_id: str = Field(min_length=3, max_length=64)
    consent_version: str = Field(min_length=1, max_length=32)
    accepted_items: list[str]
    accepted: bool

class MisclassificationReportIn(BaseModel):
    prediction_id: str
    report_type: str
    description: str = Field(default="", max_length=1000)

class IntegratedReviewIn(BaseModel):
    final_region: str
    final_findings: list[str] = []
    comment: str = Field(default="",max_length=2000)
