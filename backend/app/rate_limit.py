"""Simple in-memory per-user/IP rate limit for chat."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import get_settings

_lock = Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    limit = get_settings().chat_rate_limit_per_minute
    now = time.time()
    window = 60.0
    with _lock:
        q = _buckets[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded — slow down chat a bit",
            )
        q.append(now)


def client_key(request: Request, user_id: int | None = None) -> str:
    if user_id is not None:
        return f"user:{user_id}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"
