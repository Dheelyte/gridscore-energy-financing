"""arq task: scheduled data-retention purge of derived artefacts."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retention import purge_derived_data

log = get_logger("app.workers.retention")


async def purge_retention(ctx: dict[str, Any]) -> dict[str, int]:
    """Delete derived rows older than the configured retention window."""
    factory: async_sessionmaker[Any] = ctx["sessionmaker"]
    retention_days = get_settings().retention_days
    async with factory() as session:
        result = await purge_derived_data(session, retention_days=retention_days)
        await session.commit()
    log.info(
        "retention_purge_done",
        cutoff=result.cutoff.isoformat(),
        feature_snapshots=result.feature_snapshots,
        score_results=result.score_results,
        cooperative_lifts=result.cooperative_lifts,
    )
    return {
        "feature_snapshots": result.feature_snapshots,
        "score_results": result.score_results,
        "cooperative_lifts": result.cooperative_lifts,
    }
