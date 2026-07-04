"""Operator portfolio summary — real aggregates over the operator's own scores.

Aggregates the *latest* score per customer (from ``score_result``) for the
requesting operator: risk-tier mix, approval rate, average PD, and a documented
**estimated losses avoided** heuristic. Stage 8 adds cross-operator lender
analytics; this is the operator's own book.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import Principal, get_principal, get_session, get_settings_dep
from app.core.config import Settings
from app.db.models import Customer, ScoreResult
from app.domain.enums import RiskTier

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# A representative PAYG solar loan size (USD) for the losses-avoided estimate.
_REPRESENTATIVE_LOAN_USD = 200.0


class PortfolioSummary(BaseModel):
    total_customers: int
    scored_customers: int
    tier_distribution: dict[str, int]
    approval_rate: float
    average_default_probability: float
    estimated_losses_avoided_usd: float


async def _latest_scores(session: AsyncSession, operator_id: UUID) -> list[ScoreResult]:
    """The most recent pooled score per customer of this operator."""
    ranked = (
        select(
            ScoreResult,
            func.row_number()
            .over(
                partition_by=ScoreResult.customer_id,
                order_by=ScoreResult.created_at.desc(),
            )
            .label("rn"),
        )
        .join(Customer, Customer.id == ScoreResult.customer_id)
        .where(Customer.home_operator_id == operator_id)
        .subquery()
    )
    latest_ids = select(ranked.c.id).where(ranked.c.rn == 1)
    result = await session.scalars(select(ScoreResult).where(ScoreResult.id.in_(latest_ids)))
    return list(result.all())


@router.get("/summary", response_model=PortfolioSummary, summary="Operator portfolio summary")
async def portfolio_summary(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> PortfolioSummary:
    operator_id = principal.operator_id
    if operator_id is None:
        return PortfolioSummary(
            total_customers=0,
            scored_customers=0,
            tier_distribution={t.value: 0 for t in RiskTier},
            approval_rate=0.0,
            average_default_probability=0.0,
            estimated_losses_avoided_usd=0.0,
        )

    total = await session.scalar(
        select(func.count()).select_from(Customer).where(Customer.home_operator_id == operator_id)
    )
    scores = await _latest_scores(session, operator_id)

    tiers = {t.value: 0 for t in RiskTier}
    approved = 0
    losses_avoided = 0.0
    threshold = settings.decision_threshold
    for s in scores:
        tiers[s.risk_tier.value] += 1
        if s.default_probability < threshold:
            approved += 1
        else:
            # A loan we declined that would likely have gone bad.
            losses_avoided += s.default_probability * _REPRESENTATIVE_LOAN_USD

    n = len(scores)
    return PortfolioSummary(
        total_customers=int(total or 0),
        scored_customers=n,
        tier_distribution=tiers,
        approval_rate=(approved / n) if n else 0.0,
        average_default_probability=(sum(s.default_probability for s in scores) / n) if n else 0.0,
        estimated_losses_avoided_usd=round(losses_avoided, 2),
    )
