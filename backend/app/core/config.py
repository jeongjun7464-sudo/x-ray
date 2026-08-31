from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
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
    model_version: str = "dummy-v1"
    code_version: str = "0.3.0"
    retention_days: int | None = None
    log_level: str = "INFO"
    llm_provider: str = "dummy"
    llm_model: str = "deterministic-agent-v1"
    agent_max_steps: int = 12
    agent_timeout_seconds: int = 15
    agent_retention_days: int = 30
    agent_daily_cost_limit_usd: float = 0.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
