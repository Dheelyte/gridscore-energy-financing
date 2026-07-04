"""Persist a generated population through the Stage 1 schema (bulk inserts)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ConsentRecord,
    Customer,
    EnrichmentSignal,
    Operator,
    RepaymentEvent,
    SyntheticCustomerProfile,
)
from app.db.types import uuid7
from app.domain.enums import OperatorStatus
from app.ml.data_gen.generator import GeneratedPopulation

# Tables wiped by ``reset`` before a reseed (TRUNCATE ... CASCADE handles order).
_SEED_TABLES = (
    "synthetic_customer_profile",
    "repayment_event",
    "enrichment_signal",
    "consent_record",
    "feature_snapshot",
    "score_result",
    "cooperative_lift",
    "customer",
    "api_credential",
    "user_account",
    "operator",
)


@dataclass
class SeedSummary:
    operators: int
    customers: int
    repayment_events: int
    enrichment_signals: int
    consent_records: int
    default_rate: float
    demo_customer_id: UUID
    demo_identity_hash: str
    operator_ids: dict[int, UUID]


class SyntheticDataWriter:
    """Writes a :class:`GeneratedPopulation` to the database efficiently."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reset(self) -> None:
        """Truncate all seedable tables (dev/demo convenience)."""
        await self.session.execute(
            text(f"TRUNCATE TABLE {', '.join(_SEED_TABLES)} RESTART IDENTITY CASCADE")
        )

    async def write(self, population: GeneratedPopulation) -> SeedSummary:
        operator_ids = await self._write_operators(population)
        customer_ids = await self._write_customers(population, operator_ids)
        n_events = await self._write_events(population, operator_ids, customer_ids)
        n_signals = await self._write_signals(population, customer_ids)
        n_consents = await self._write_consents(population, customer_ids)
        await self._write_profiles(population, customer_ids)

        demo = next(c for c in population.customers if c.is_demo)
        return SeedSummary(
            operators=len(population.operators),
            customers=len(population.customers),
            repayment_events=n_events,
            enrichment_signals=n_signals,
            consent_records=n_consents,
            default_rate=population.default_rate,
            demo_customer_id=customer_ids[id(demo)],
            demo_identity_hash=demo.identity_hash,
            operator_ids=operator_ids,
        )

    # -- per-entity writers ------------------------------------------------ #
    async def _write_operators(self, pop: GeneratedPopulation) -> dict[int, UUID]:
        ids: dict[int, UUID] = {}
        for ref, spec in enumerate(pop.operators):
            op = Operator(name=spec.name, country=spec.country, status=OperatorStatus.ACTIVE)
            self.session.add(op)
            await self.session.flush()
            ids[ref] = op.id
        return ids

    async def _write_customers(
        self, pop: GeneratedPopulation, operator_ids: dict[int, UUID]
    ) -> dict[int, UUID]:
        # Keyed by id() of the GeneratedCustomer so children can resolve FKs.
        customer_ids: dict[int, UUID] = {}
        rows = []
        for c in pop.customers:
            cid = uuid7()
            customer_ids[id(c)] = cid
            rows.append(
                {
                    "id": cid,
                    "identity_hash": c.identity_hash,
                    "home_operator_id": operator_ids[c.home_operator_ref],
                }
            )
        await self.session.execute(insert(Customer), rows)
        return customer_ids

    async def _write_events(
        self,
        pop: GeneratedPopulation,
        operator_ids: dict[int, UUID],
        customer_ids: dict[int, UUID],
    ) -> int:
        rows = [
            {
                "id": uuid7(),
                "operator_id": operator_ids[ev.operator_ref],
                "customer_id": customer_ids[id(c)],
                "instalment_amount": ev.instalment_amount,
                "currency": ev.currency,
                "due_date": ev.due_date,
                "paid_date": ev.paid_date,
                "status": ev.status,
            }
            for c in pop.customers
            for ev in c.events
        ]
        if rows:
            await self.session.execute(insert(RepaymentEvent), rows)
        return len(rows)

    async def _write_signals(self, pop: GeneratedPopulation, customer_ids: dict[int, UUID]) -> int:
        rows = [
            {
                "id": uuid7(),
                "customer_id": customer_ids[id(c)],
                "provider_type": s.provider_type,
                "payload_json": s.payload,
                "captured_at": s.captured_at,
            }
            for c in pop.customers
            for s in c.signals
        ]
        if rows:
            await self.session.execute(insert(EnrichmentSignal), rows)
        return len(rows)

    async def _write_consents(self, pop: GeneratedPopulation, customer_ids: dict[int, UUID]) -> int:
        rows = [
            {
                "id": uuid7(),
                "customer_id": customer_ids[id(c)],
                "scope": cons.scope,
                "granted": cons.granted,
                "source": cons.source,
                "granted_at": cons.granted_at,
                "expires_at": cons.expires_at,
            }
            for c in pop.customers
            for cons in c.consents
        ]
        if rows:
            await self.session.execute(insert(ConsentRecord), rows)
        return len(rows)

    async def _write_profiles(
        self, pop: GeneratedPopulation, customer_ids: dict[int, UUID]
    ) -> None:
        rows = [
            {
                "id": uuid7(),
                "customer_id": customer_ids[id(c)],
                "default_label": c.default_label,
                "default_probability_true": c.default_probability_true,
                "latent_features_json": c.latent_features,
                "is_demo": c.is_demo,
                "scenario": c.scenario,
            }
            for c in pop.customers
        ]
        await self.session.execute(insert(SyntheticCustomerProfile), rows)
