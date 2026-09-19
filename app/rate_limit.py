"""Simple in-process rate limiting for the authentication endpoints.

Deliberately dependency-free: a fixed-window counter keyed by client host.
This is sufficient for a single-process deployment.

Limits of this approach (read before relying on it in production):

- Behind a proxy / serverless platform the direct peer address is the proxy,
  so the key is derived from X-Forwarded-For when present (first entry).
  X-Forwarded-For is client-spoofable — treat this as best-effort abuse
  reduction, not a security boundary against a determined attacker who can
  rotate identities.
- Buckets live in process memory: multiple workers, containers, or serverless
  instances (e.g. Vercel cold starts) each get their own counters, so the
  effective limit is ``limit x instances`` and resets on restart. Use a
  shared store (Redis / slowapi with a shared backend) or platform-level
  rate limiting when running more than one process.
"""

import inspect
import threading
import time
from collections.abc import Awaitable, Callable

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


def client_key(request: Request) -> str:
    """Best-effort per-client identity for rate-limit buckets.

    Prefers the leftmost X-Forwarded-For entry (the original client as seen
    by the outermost trusted proxy) and falls back to the direct peer
    address. Without this, every request behind a proxy/serverless gateway
    shares one bucket and legitimate users 429 each other.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client:
        return request.client.host
    return "unknown"


# Optional bucket-key component: sync or async callable taking the request.
KeyFunc = Callable[[Request], str | Awaitable[str]]


def rate_limit(
    prefix: str, limit: int, window_seconds: int, *, key: KeyFunc | None = None
):
    """Build a FastAPI dependency that rejects requests over the limit with 429.

    The bucket is f"{prefix}:{client}:{key(...)}" — pass key= for a
    per-account component (e.g. the login username) so one account's traffic
    neither shields nor starves another's.
    """

    async def dependency(request: Request) -> None:
        suffix = client_key(request)
        if key is not None:
            extra = key(request)
            if inspect.isawaitable(extra):
                extra = await extra
            suffix = f"{suffix}:{extra}"
        if not rate_limiter.allow(f"{prefix}:{suffix}", limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency