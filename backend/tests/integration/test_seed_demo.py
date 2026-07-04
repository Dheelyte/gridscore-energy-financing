"""Integration tests for seeding the synthetic population into PostgreSQL."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, RepaymentEvent, SyntheticCustomerProfile
from app.db.repositories import CustomerRepository, RepaymentEventRepository
from app.ml.data_gen import GeneratorConfig, SyntheticGenerator
from app.ml.data_gen.seed import seed_population

pytestmark = pytest.mark.integration

_CONFIG = GeneratorConfig(n_customers=120, seed=99)


async def test_seed_populates_all_tables(session: AsyncSession) -> None:
    population, summary = await seed_population(session, _CONFIG, reset=True)

    assert summary.operators == _CONFIG.n_operators
    assert summary.customers == _CONFIG.n_customers + 1  # + demo
    assert summary.repayment_events > 0
    assert summary.enrichment_signals == summary.customers * 3

    db_customers = await session.scalar(sa.select(sa.func.count()).select_from(Customer))
    db_events = await session.scalar(sa.select(sa.func.count()).select_from(RepaymentEvent))
    assert db_customers == summary.customers
    assert db_events == summary.repayment_events


async def test_persisted_default_rate_in_range(session: AsyncSession) -> None:
    await seed_population(session, _CONFIG, reset=True)
    total = (
        await session.scalar(sa.select(sa.func.count()).select_from(SyntheticCustomerProfile)) or 0
    )
    defaults = (
        await session.scalar(
            sa.select(sa.func.count()).where(SyntheticCustomerProfile.default_label.is_(True))
        )
        or 0
    )
    assert total == _CONFIG.n_customers + 1
    rate = defaults / total
    assert 0.08 <= rate <= 0.22


async def test_demo_customer_persisted_with_solo_pooled_split(session: AsyncSession) -> None:
    await seed_population(session, _CONFIG, reset=True)

    demo_hash = SyntheticGenerator.demo_identity_hash()
    customer = await CustomerRepository(session).get_by_identity_hash(demo_hash)
    assert customer is not None

    profile = await session.scalar(
        sa.select(SyntheticCustomerProfile).where(
            SyntheticCustomerProfile.customer_id == customer.id
        )
    )
    assert profile is not None
    assert profile.is_demo is True
    assert profile.scenario == "borderline_flip"

    # Pooled history (all operators) is strictly larger than the solo (home) view.
    repo = RepaymentEventRepository(session)
    pooled = await repo.list_for_customer(customer.id)
    solo = await repo.list_for_customer_solo(customer.id, customer.home_operator_id)
    assert len(solo) < len(pooled)

    def on_time_rate(events: list[RepaymentEvent]) -> float:
        from app.domain.enums import RepaymentStatus

        return sum(e.status is RepaymentStatus.ON_TIME for e in events) / len(events)

    # The solo view looks risky; the pooled view looks safe — the flip setup.
    assert on_time_rate(solo) < 0.5
    assert on_time_rate(pooled) > 0.85


async def test_reset_makes_reseed_idempotent(session: AsyncSession) -> None:
    await seed_population(session, _CONFIG, reset=True)
    await seed_population(session, _CONFIG, reset=True)  # should TRUNCATE, not stack
    count = await session.scalar(sa.select(sa.func.count()).select_from(Customer))
    assert count == _CONFIG.n_customers + 1
