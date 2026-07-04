"""Helpers to enqueue jobs onto the arq queue from the API process."""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import Settings


async def create_arq_pool(settings: Settings) -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


async def enqueue_ingest(pool: ArqRedis, payload: dict[str, Any]) -> str:
    """Enqueue an ingestion batch; returns the arq job id."""
    job = await pool.enqueue_job("ingest_batch", payload)
    return job.job_id if job is not None else ""
