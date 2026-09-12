RETRYABLE_HTTP = {429, 502, 503, 504}

def retry_delay(attempt: int, max_attempts: int = 3, base_seconds: float = 2) -> float | None:
    if not 1 <= attempt < max_attempts:
        return None
    return min(300, max(0.1, base_seconds) * 2 ** (attempt - 1))
