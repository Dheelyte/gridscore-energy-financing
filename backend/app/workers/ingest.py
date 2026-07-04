"""arq task: process an ingestion batch off the request path.

The task is a thin wrapper that opens a DB session, runs the shared
:func:`process_ingestion` pipeline, commits, and returns the report. It is
**idempotent** (dedup on customer/operator/due_date), so retries are safe."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.ingestion.pipeline import process_ingestion

log = get_logger("app.workers.ingest")


async def ingest_batch(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """arq job entrypoint. ``payload`` carries ``operator_id`` and ``rows``."""
    factory: async_sessionmaker[Any] = ctx["sessionmaker"]
    salt: str = ctx["identity_salt"]
    operator_id = UUID(str(payload["operator_id"]))
    rows = list(payload["rows"])

    async with factory() as session:
        outcome = await process_ingestion(
            session,
            operator_id=operator_id,
            rows=rows,
            identity_salt=salt,
            enrich=bool(payload.get("enrich", True)),
        )
        await session.commit()

    log.info(
        "ingest_batch_done",
        operator_id=str(operator_id),
        inserted=outcome.report.inserted,
        duplicates=outcome.report.duplicates,
        failed=outcome.report.failed,
        enriched=outcome.customers_enriched,
    )
    return outcome.as_dict()
