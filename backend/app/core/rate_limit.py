import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    """Process-local limiter. Replace with Redis for multi-instance deployment."""

    def __init__(self, requests: int, window_seconds: int = 60):
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - self.window_seconds:
                events.popleft()
            if len(events) >= self.requests:
                return False
            events.append(now)
            return True
