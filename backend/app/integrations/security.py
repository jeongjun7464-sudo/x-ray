import hashlib
from urllib.parse import urlsplit

def anonymous_uid(value: str) -> str:
    if not value:
        raise ValueError("UID_REQUIRED")
    return hashlib.sha256(value.encode()).hexdigest()

def url_policy(url: str, verify_tls: bool, production: bool) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "INVALID_ENDPOINT"
    if production and (parsed.scheme != "https" or not verify_tls):
        return "TLS_REQUIRED"
    if not production and parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1", "orthanc"}:
        return "TLS_REQUIRED"
    return None

def masked_endpoint(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://[configured-host]" if parsed.hostname else "NOT_CONFIGURED"

def demo_endpoint(url: str) -> bool:
    return urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1", "orthanc"}
