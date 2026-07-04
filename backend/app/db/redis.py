"""Async Redis client factory.

Redis backs caching, rate-limit counters, and the arq job broker in later
stages. Stage 1 uses it only for the readiness probe, but the client is created
here so the wiring is in one place."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings


def create_redis(settings: Settings) -> Redis:
    """Create an async Redis client from settings. Connects lazily."""
    client: Redis = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return client
