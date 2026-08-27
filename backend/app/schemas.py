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
class ReviewUpdate(BaseModel):
    corrected_region: str
    comment: str = Field(default="", max_length=1000)
class ValidationOut(BaseModel):
    valid: bool
    file_format: str
    width: int
    height: int
    message: str
