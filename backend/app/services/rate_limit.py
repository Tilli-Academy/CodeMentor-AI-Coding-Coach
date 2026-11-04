"""
In-memory, per-client rate limiting for the AI endpoints.

CodeMentor runs locally for a single user, so this is deliberately minimal: it
guards the expensive local-model calls against runaway/accidental floods (e.g. a
buggy client loop hammering Ollama), not multi-tenant abuse. It needs no external
dependency and no shared store.

Algorithm: a sliding window per client. Each client key keeps a deque of recent
request timestamps; on each call we drop timestamps older than the window and
reject (HTTP 429) once the remaining count reaches the limit.

Thread-safety: FastAPI runs the sync route handlers in a threadpool, so the
shared state is guarded by a lock. `time.monotonic()` is used so the window is
immune to wall-clock changes.
"""
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """A fixed-size sliding-window limiter keyed by an opaque client string."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record a request for `key`; raise HTTP 429 if it exceeds the limit."""
        # A non-positive limit disables limiting (useful to turn the feature off).
        if self.max_requests <= 0:
            return

        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                # Seconds until the oldest in-window hit expires and a slot frees.
                retry_after = max(1, int(hits[0] + self.window_seconds - now) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests — please slow down and try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        """Forget all recorded requests (used by tests)."""
        with self._lock:
            self._hits.clear()


def _client_key(request: Request) -> str:
    """Identify the caller. Honour X-Forwarded-For (the dev proxy) when present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Singleton limiter, configured from the environment with local-friendly defaults.
rate_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30")),
    window_seconds=float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
)


def rate_limit(request: Request) -> None:
    """FastAPI dependency: enforce the per-client request rate on AI endpoints."""
    rate_limiter.check(_client_key(request))
