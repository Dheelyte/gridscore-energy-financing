"""Redis-backed rate limiter (against an in-memory fake Redis)."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from app.core.ratelimit import RateLimiter

pytestmark = pytest.mark.unit


async def test_allows_up_to_limit_then_blocks() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = RateLimiter(redis, limit=3, window_seconds=60)

    decisions = [await limiter.hit("user:1") for _ in range(4)]
    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert decisions[0].remaining == 2
    assert decisions[-1].remaining <= 0
    assert decisions[-1].headers()["Retry-After"]


async def test_limits_are_per_identity() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = RateLimiter(redis, limit=1, window_seconds=60)
    assert (await limiter.hit("a")).allowed is True
    assert (await limiter.hit("b")).allowed is True  # different identity, own budget
    assert (await limiter.hit("a")).allowed is False


async def test_fails_open_when_redis_unavailable() -> None:
    class BrokenRedis:
        async def incr(self, *_: object) -> int:
            raise ConnectionError("redis down")

    limiter = RateLimiter(BrokenRedis(), limit=1, window_seconds=60)  # type: ignore[arg-type]
    decision = await limiter.hit("x")
    assert decision.allowed is True  # availability over strict enforcement
