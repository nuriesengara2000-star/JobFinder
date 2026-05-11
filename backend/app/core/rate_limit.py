from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Simple per-IP sliding-window rate limiter.

    This is enough for the first production-ready version and can later be
    replaced with Redis when the app is deployed with multiple workers.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, Deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self.window_seconds
        history = self._requests[client_ip]

        while history and history[0] < window_start:
            history.popleft()

        if len(history) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

        history.append(now)
