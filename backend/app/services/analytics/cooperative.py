"""Cooperative-wide aggregates: health, lender portfolio, and audit search.

All figures come from real rows (counts, the latest score per customer, the
materialised cooperative-lift table) — nothing is hard-coded."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    ConsentRecord,
    CooperativeLift,
    Customer,
    EnrichmentSignal,
    Operator,
    RepaymentEvent,
    ScoreResult,
)
from app.domain.enums import RiskTier

# Representative PAYG solar loan size (USD) for the debt-capacity heuristic.
REPRESENTATIVE_LOAN_USD = 200.0
# PD histogram bin edges.
_PD_BINS = [0.0, 0.05, 0.10, 0.20, 0.35, 1.01]


@dataclass
class CooperativeHealth:
    operators: int
    customers: int
    repayment_events: int
    enrichment_signals: int
    scored_customers: int
    active_consents: int
    cooperative_lifts: int


async def _count(session: AsyncSession, model: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def cooperative_health(session: AsyncSession) -> CooperativeHealth:
    scored = await session.scalar(select(func.count(func.distinct(ScoreResult.customer_id))))
    return CooperativeHealth(
        operators=await _count(session, Operator),
        customers=await _count(session, Customer),
        repayment_events=await _count(session, RepaymentEvent),
        enrichment_signals=await _count(session, EnrichmentSignal),
        scored_customers=int(scored or 0),
        active_consents=await _count(session, ConsentRecord),
        cooperative_lifts=await _count(session, CooperativeLift),
    )


@dataclass
class LenderPortfolio:
    scored_customers: int
    average_default_probability: float
    approval_rate: float
    pd_histogram: list[dict[str, float | int]]
    tier_distribution: dict[str, int]
    operator_concentration: list[dict[str, object]]
    newly_bankable_customers: int
    estimated_debt_capacity_unlocked_usd: float
    extras: dict[str, object] = field(default_factory=dict)


async def _latest_scores(session: AsyncSession) -> list[ScoreResult]:
    ranked = select(
        ScoreResult.id,
        func.row_number()
        .over(
            partition_by=ScoreResult.customer_id,
            order_by=ScoreResult.created_at.desc(),
        )
        .label("rn"),
    ).subquery()
    latest_ids = select(ranked.c.id).where(ranked.c.rn == 1)
    result = await session.scalars(select(ScoreResult).where(ScoreResult.id.in_(latest_ids)))
    return list(result.all())


async def lender_portfolio(session: AsyncSession, *, threshold: float) -> LenderPortfolio:
    scores = await _latest_scores(session)
    n = len(scores)

    tiers = {t.value: 0 for t in RiskTier}
    bins = [0 for _ in range(len(_PD_BINS) - 1)]
    approved = 0
    for s in scores:
        tiers[s.risk_tier.value] += 1
        if s.default_probability < threshold:
            approved += 1
        for b in range(len(_PD_BINS) - 1):
            if _PD_BINS[b] <= s.default_probability < _PD_BINS[b + 1]:
                bins[b] += 1
                break
    histogram = [
        {"from": _PD_BINS[b], "to": min(_PD_BINS[b + 1], 1.0), "count": bins[b]}
        for b in range(len(_PD_BINS) - 1)
    ]

    # Operator concentration (share of customers by home operator).
    rows = await session.execute(
        select(Operator.name, func.count(Customer.id))
        .join(Customer, Customer.home_operator_id == Operator.id)
        .group_by(Operator.name)
        .order_by(func.count(Customer.id).desc())
    )
    counts = list(rows.all())
    total_customers = sum(c for _, c in counts) or 1
    concentration = [
        {"operator": name, "customers": int(c), "share": round(c / total_customers, 4)}
        for name, c in counts
    ]

    # Customers the cooperative made bankable: solo would reject, pooled approves.
    bankable = await session.scalar(
        select(func.count())
        .select_from(CooperativeLift)
        .where(CooperativeLift.solo_pd >= threshold, CooperativeLift.pooled_pd < threshold)
    )
    bankable = int(bankable or 0)

    return LenderPortfolio(
        scored_customers=n,
        average_default_probability=(sum(s.default_probability for s in scores) / n) if n else 0.0,
        approval_rate=(approved / n) if n else 0.0,
        pd_histogram=histogram,
        tier_distribution=tiers,
        operator_concentration=concentration,
        newly_bankable_customers=bankable,
        estimated_debt_capacity_unlocked_usd=round(bankable * REPRESENTATIVE_LOAN_USD, 2),
    )


async def audit_search(
    session: AsyncSession,
    *,
    actor: str | None = None,
    action: str | None = None,
    limit: int = 50,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if actor:
        stmt = stmt.where(AuditLog.actor.ilike(f"%{actor}%"))
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    result = await session.scalars(stmt)
    return list(result.all())
