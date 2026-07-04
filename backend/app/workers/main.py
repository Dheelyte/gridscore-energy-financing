"""arq worker entrypoint.

    arq app.workers.main.WorkerSettings

Brings up the async-native background worker (ADR-0006) that processes ingestion
jobs. The DB engine + session factory are created once on startup and shared via
the job context.
"""

from __future__ import annotations

from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import create_engine, create_session_factory
from app.workers.ingest import ingest_batch
from app.workers.retention import purge_retention


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def _on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    ctx["engine"] = engine
    ctx["sessionmaker"] = create_session_factory(engine)
    ctx["identity_salt"] = settings.identity_hash_salt.get_secret_value()
    get_logger("app.workers").info("worker_startup")


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()
    get_logger("app.workers").info("worker_shutdown")


class WorkerSettings:
    functions: ClassVar = [ingest_batch, purge_retention]
    cron_jobs: ClassVar = [cron(purge_retention, hour=3, minute=0)]  # nightly purge
    redis_settings = _redis_settings()
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    max_jobs = 10
    keep_result = 3600  # seconds; lets the API poll job results
