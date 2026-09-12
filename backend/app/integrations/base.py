from typing import Protocol
import ssl
import httpx
from .schemas import AdapterConfig, IntegrationResult
from .security import demo_endpoint, url_policy
from .retry import RETRYABLE_HTTP

class PacsAdapter(Protocol):
    def health_check(self): ...
    def search_studies(self, query): ...
    def search_series(self, query): ...
    def retrieve_instance(self, instance_id): ...
    def store_instance(self, data, idempotency_key, confirmed=False): ...
    def store_report(self, data, idempotency_key, confirmed=False): ...
    def get_capabilities(self): ...

class HttpAdapter:
    provider = "INTEGRATION"
    def __init__(self, config: AdapterConfig | None = None, *, transport=None):
        self.config = config or AdapterConfig()
        self.transport = transport

    def request(self, method, path, *, confirmed=False, idempotency_key=None, headers=None, **kwargs):
        cfg = self.config
        if not cfg.enabled or not cfg.base_url:
            return IntegrationResult("NOT_CONFIGURED", self.provider + "_NOT_CONFIGURED")
        problem = url_policy(cfg.base_url, cfg.verify_tls, cfg.production)
        if problem:
            return IntegrationResult("CERTIFICATE_ERROR" if problem == "TLS_REQUIRED" else "DISCONNECTED", self.provider + "_" + problem)
        mode = "DEMO" if demo_endpoint(cfg.base_url) else "CONFIGURED"
        if not path.startswith("/") or path.startswith("//") or ".." in path or "?" in path or "#" in path:
            return IntegrationResult("DISCONNECTED", self.provider + "_INVALID_PATH", mode=mode)
        if method not in {"GET", "HEAD"} and not kwargs.pop("read_only", False):
            if not cfg.transmission_enabled or (mode == "DEMO" and not cfg.allow_demo_transmission):
                return IntegrationResult("MANUAL_REVIEW_REQUIRED", self.provider + "_TRANSMISSION_DISABLED", mode=mode)
            if not confirmed or not idempotency_key:
                return IntegrationResult("MANUAL_REVIEW_REQUIRED", self.provider + "_CONFIRMATION_REQUIRED", mode=mode)
        request_headers = dict(headers or {})
        if cfg.token:
            request_headers["Authorization"] = "Bearer " + cfg.token
        if idempotency_key:
            request_headers["Idempotency-Key"] = idempotency_key
        auth = (cfg.username, cfg.password) if cfg.username else None
        try:
            with httpx.Client(transport=self.transport, verify=cfg.verify_tls, timeout=cfg.timeout, follow_redirects=False, trust_env=False) as client:
                with client.stream(method, cfg.base_url.rstrip("/") + path, headers=request_headers, auth=auth, **kwargs) as response:
                    code = response.status_code
                    if code in {401, 403}:
                        return IntegrationResult("AUTHENTICATION_REQUIRED", self.provider + "_AUTH_FAILED", http_status=code, mode=mode)
                    if code == 404:
                        return IntegrationResult("DISCONNECTED", self.provider + "_RESOURCE_NOT_FOUND", http_status=code, mode=mode)
                    if code == 409:
                        return IntegrationResult("DEGRADED", self.provider + "_DUPLICATE_INSTANCE", http_status=code, mode=mode)
                    if code >= 300:
                        return IntegrationResult("DEGRADED", self.provider + "_HTTP_ERROR", http_status=code, retryable=code in RETRYABLE_HTTP, mode=mode)
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > cfg.max_response_bytes:
                            return IntegrationResult("DEGRADED", self.provider + "_RESPONSE_TOO_LARGE", mode=mode)
                    return IntegrationResult("CONNECTED", data={"bytes": bytes(data), "content_type": response.headers.get("content-type", "")}, http_status=code, mode=mode)
        except httpx.TimeoutException:
            return IntegrationResult("DEGRADED", self.provider + "_TIMEOUT", retryable=True, mode=mode)
        except (httpx.TransportError, ssl.SSLError) as exc:
            chain = exc
            tls = isinstance(exc, ssl.SSLError)
            for _ in range(8):
                if chain is None:
                    break
                tls = tls or isinstance(chain, ssl.SSLError)
                chain = chain.__cause__
            return IntegrationResult("CERTIFICATE_ERROR" if tls else "DISCONNECTED", self.provider + ("_TLS_ERROR" if tls else "_NETWORK_ERROR"), retryable=not tls, mode=mode)

    def json_result(self, result, expected_type):
        import json
        if result.status != "CONNECTED":
            return result
        try:
            if "json" not in result.data["content_type"]:
                raise ValueError()
            value = json.loads(result.data["bytes"])
            if not isinstance(value, expected_type):
                raise ValueError()
            return IntegrationResult("CONNECTED", data=value, http_status=result.http_status, mode=result.mode)
        except (ValueError, KeyError):
            return IntegrationResult("DEGRADED", self.provider + "_INVALID_RESPONSE", mode=result.mode)
