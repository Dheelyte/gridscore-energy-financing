"""The ingestion → enrichment pipeline, shared by the inline API path and the
background worker so both behave identically."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ingestion.enrichment import EnrichmentService
from app.services.ingestion.schemas import IngestionReport
from app.services.ingestion.service import IngestionService


@dataclass
class PipelineOutcome:
    report: IngestionReport
    affected_customer_ids: set[UUID]
    customers_enriched: int
    signals_written: int

    def as_dict(self) -> dict[str, object]:
        return {
            "report": self.report.model_dump(mode="json"),
            "customers_enriched": self.customers_enriched,
            "signals_written": self.signals_written,
        }


async def process_ingestion(
    session: AsyncSession,
    *,
    operator_id: UUID,
    rows: list[dict[str, object]],
    identity_salt: str,
    enrich: bool = True,
) -> PipelineOutcome:
    ingestion = IngestionService(session, identity_salt=identity_salt)
    result = await ingestion.ingest_rows(rows, operator_id)

    enriched = 0
    signals = 0
    if enrich and result.affected_customer_ids:
        enrichment = EnrichmentService(session)
        for res in await enrichment.enrich_many(result.affected_customer_ids):
            if res.enriched:
                enriched += 1
                signals += res.signals_written

    return PipelineOutcome(
        report=result.report,
        affected_customer_ids=result.affected_customer_ids,
        customers_enriched=enriched,
        signals_written=signals,
    )
