"""Redis-backed fixed-window rate limiter.

A simple, predictable INCR-with-EXPIRE fixed window keyed per principal. Returns
the decision plus the headers clients expect (``X-RateLimit-*`` / ``Retry-After``).
Fail-open: if Redis is unavailable we allow the request rather than hard-failing
the API (availability over strict enforcement for this prototype).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int

    def headers(self) -> dict[str, str]:
        h = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Reset": str(self.reset_seconds),
        }
        if not self.allowed:
            h["Retry-After"] = str(self.reset_seconds)
        return h


class RateLimiter:
    def __init__(self, redis: Redis, *, limit: int, window_seconds: int) -> None:
        self.redis = redis
        self.limit = limit
        self.window = window_seconds

    async def hit(self, identity: str) -> RateLimitDecision:
        window_id = int(time.time()) // self.window
        key = f"ratelimit:{identity}:{window_id}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, self.window)
        except Exception:
            # Fail open — never take the whole API down because Redis blipped.
            return RateLimitDecision(True, self.limit, self.limit, self.window)

        remaining = self.limit - int(count)
        reset = self.window - (int(time.time()) % self.window)
        return RateLimitDecision(remaining >= 0, self.limit, remaining, reset)
