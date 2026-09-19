"""Simple in-process rate limiting for the authentication endpoints.

Deliberately dependency-free: a fixed-window counter keyed by client host.
This is sufficient for a single-process deployment; swap for a shared store
(Redis / slowapi) when running multiple workers or instances, where an
in-memory counter would be split across processes.
"""

import threading
import time

from fastapi import HTTPException, Request, status


class _Window:
    __slots__ = ("start", "count")

    def __init__(self, start: float, count: int = 1) -> None:
        self.start = start
        self.count = count


class InMemoryRateLimiter:
    """Fixed-window limiter keyed by an arbitrary string (IP + endpoint)."""

    def __init__(self) -> None:
        self._buckets: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now - bucket.start >= window_seconds:
                self._prune(now)
                self._buckets[key] = _Window(now)
                return True
            if bucket.count >= limit:
                return False
            bucket.count += 1
            return True

    def clear(self) -> None:
        """Drop every counter (used by tests to keep cases isolated)."""
        with self._lock:
            self._buckets.clear()

    def _prune(self, now: float) -> None:
        # Opportunistic cleanup keeps memory bounded when many clients appear.
        if len(self._buckets) < 10_000:
            return
        expired = [
            key
            for key, window in self._buckets.items()
            if now - window.start >= 600
        ]
        for key in expired:
            del self._buckets[key]


rate_limiter = InMemoryRateLimiter()


def rate_limit(prefix: str, limit: int, window_seconds: int):
    """Build a FastAPI dependency that rejects requests over the limit with 429."""

    def dependency(request: Request) -> None:
        host = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(f"{prefix}:{host}", limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

    return dependency