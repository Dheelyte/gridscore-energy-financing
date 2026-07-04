"""Enrichment job: pull provider signals for a customer and recompute features.

Runs after ingestion (and on new consent). It is **consent-gated**: a customer
without an active ``ENRICHMENT`` consent is skipped (degrade, never fail). For
each provider it stores an ``enrichment_signal`` row, then materialises a fresh
pooled ``feature_snapshot`` — the "feature recomputation" that makes the next
score reflect the new data.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EnrichmentSignal, FeatureSnapshot
from app.db.repositories import (
    ConsentRecordRepository,
    CustomerRepository,
    EnrichmentSignalRepository,
    FeatureSnapshotRepository,
)
from app.domain.enums import ConsentScope, ScoreView
from app.ml.features import FeatureExtractor
from app.providers.base import EnrichmentProvider
from app.providers.registry import default_providers
from app.services.feature_io import load_raw_customer_data


@dataclass
class EnrichmentResult:
    customer_id: UUID
    enriched: bool  # False when skipped for lack of consent
    signals_written: int
    recomputed_features: bool


class EnrichmentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        providers: list[EnrichmentProvider] | None = None,
        reference_date: dt.date | None = None,
    ) -> None:
        self.session = session
        self.providers = providers if providers is not None else default_providers()
        self.reference_date = reference_date or dt.datetime.now(dt.UTC).date()
        self.customers = CustomerRepository(session)
        self.consents = ConsentRecordRepository(session)
        self.signals = EnrichmentSignalRepository(session)
        self.snapshots = FeatureSnapshotRepository(session)
        self._extractor = FeatureExtractor()

    async def enrich_customer(self, customer_id: UUID) -> EnrichmentResult:
        customer = await self.customers.get(customer_id)
        if customer is None:
            return EnrichmentResult(
                customer_id, enriched=False, signals_written=0, recomputed_features=False
            )

        consent = await self.consents.active_for_customer(customer_id, ConsentScope.ENRICHMENT)
        if consent is None:
            return EnrichmentResult(
                customer_id, enriched=False, signals_written=0, recomputed_features=False
            )

        now = dt.datetime.now(dt.UTC)
        written = 0
        for provider in self.providers:
            payload = await provider.fetch_signal(customer.identity_hash)
            self.session.add(
                EnrichmentSignal(
                    customer_id=customer_id,
                    provider_type=provider.provider_type,
                    payload_json=payload,
                    captured_at=now,
                )
            )
            written += 1
        await self.session.flush()

        # Recompute and persist the pooled feature vector with the new signals.
        raw = await load_raw_customer_data(self.session, customer)
        features = self._extractor.extract(
            raw, ScoreView.POOLED, reference_date=self.reference_date
        )
        await self.snapshots.add(
            FeatureSnapshot(
                customer_id=customer_id,
                computed_at=now,
                features_json=features,
                view=ScoreView.POOLED,
            )
        )
        return EnrichmentResult(
            customer_id, enriched=True, signals_written=written, recomputed_features=True
        )

    async def enrich_many(self, customer_ids: set[UUID]) -> list[EnrichmentResult]:
        return [await self.enrich_customer(cid) for cid in customer_ids]
