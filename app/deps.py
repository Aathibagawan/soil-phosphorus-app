"""Shared FastAPI dependencies: client identity + tiny in-memory rate limiter."""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from .config import RATE_LIMIT_PER_MIN

_CLIENT_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def optional_client_id(x_client_id: str | None = Header(default=None)) -> str:
    """Browser-generated anonymous id (no login). Missing -> shared 'anonymous' bucket."""
    if x_client_id is None:
        return "anonymous"
    if not _CLIENT_RE.match(x_client_id):
        raise HTTPException(400, "Invalid X-Client-Id header (8-64 chars: letters, digits, _ or -).")
    return x_client_id


def required_client_id(x_client_id: str | None = Header(default=None)) -> str:
    if x_client_id is None:
        raise HTTPException(400, "X-Client-Id header is required for history endpoints.")
    return optional_client_id(x_client_id)


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    if RATE_LIMIT_PER_MIN <= 0:
        return
    ip = request.client.host if request.client else "unknown"
    now, q = time.monotonic(), _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Too many requests - please wait a minute.", headers={"Retry-After": "60"})
    q.append(now)
