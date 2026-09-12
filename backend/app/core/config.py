from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    qms_sllm_enabled: bool = False
    qms_risk_high_score: int = 10
    qms_risk_critical_score: int = 20
    environment: str = "development"
    debug: bool = False
    app_name: str = "X-Ray Anatomical Region Classification & Routing System"
    database_url: str = "sqlite:///./xray.db"
    max_upload_mb: int = 20
    min_image_dimension: int = 32
    max_image_dimension: int = 12000
    auto_classify_min_confidence: float = 0.70
    uncertainty_margin: float = 0.12
    rate_limit_per_minute: int = 60
    cors_origins: str = "http://localhost:5173"
    dummy_mode: bool = True
    pacs_provider: str = "none"
    pacs_enabled: bool = False
    orthanc_base_url: str = ""
    orthanc_username: str = ""
    orthanc_password: str = ""
    orthanc_timeout_seconds: int = 10
    orthanc_verify_tls: bool = True
    dicomweb_base_url: str = ""
    dicomweb_qido_path: str = "/studies"
    dicomweb_wado_path: str = "/studies"
    dicomweb_stow_path: str = "/studies"
    dicomweb_token: str = ""
    dicomweb_timeout_seconds: int = 15
    dicomweb_verify_tls: bool = True
    fhir_enabled: bool = False
    fhir_base_url: str = ""
    fhir_token: str = ""
    fhir_timeout_seconds: int = 15
    fhir_verify_tls: bool = True
    external_transmission_enabled: bool = False
    external_transmission_allow_demo: bool = False
    external_max_retries: int = 3
    external_retry_base_seconds: int = 2
    integration_store_raw_uids: bool = False
    integration_audit_enabled: bool = True
    integration_principal_institutions: dict[str, str] = {}
    integration_resource_institutions: dict[str, str] = {}
    integration_connection_institution_id: str = ""
    model_version: str = "dummy-v1"
    code_version: str = "0.3.0"
    retention_days: int | None = None
    log_level: str = "INFO"
    llm_provider: str = "dummy"
    llm_model: str = "deterministic-agent-v1"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_model_name: str = "Qwen2.5-7B-Instruct"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 60
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.1
    llm_max_retries: int = 1
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "xray_knowledge"
    qdrant_vector_size: int = 384
    embedding_provider: str = "deterministic-local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retrieval_top_k: int = 8
    retrieval_final_k: int = 5
    rrf_k: int = 60
    auth_enforced: bool = False
    auth_allow_legacy_headers: bool = True
    auth_demo_tokens_enabled: bool = True
    auth_session_secret: str = ""
    auth_session_ttl_seconds: int = 900
    auth_public_paths: str = "/api/health,/api/model/info,/api/classes,/docs,/openapi.json,/redoc"
    agent_max_steps: int = 12
    agent_timeout_seconds: int = 15
    agent_retention_days: int = 30
    agent_daily_cost_limit_usd: float = 0.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
