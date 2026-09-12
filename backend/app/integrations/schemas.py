from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class IntegrationResult:
    status: str
    code: str | None = None
    data: Any = None
    http_status: int | None = None
    retryable: bool = False
    mode: str = "UNCONFIGURED"

@dataclass(frozen=True)
class AdapterConfig:
    base_url: str = ""
    enabled: bool = False
    verify_tls: bool = True
    production: bool = False
    timeout: float = 10
    max_response_bytes: int = 20 * 1024 * 1024
    transmission_enabled: bool = False
    allow_demo_transmission: bool = False
    token: str = field(default="", repr=False)
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
