"""Lender/DFI analytics: cross-operator portfolio risk and the network effect."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.v1.deps import Principal, get_session, get_settings_dep, require_roles
from app.core.config import Settings
from app.domain.enums import UserRole
from app.ml.data_gen.config import GeneratorConfig
from app.services.analytics.cooperative import lender_portfolio
from app.services.analytics.network_effect import compute_network_effect

router = APIRouter(prefix="/analytics", tags=["analytics"])

_lender = require_roles(UserRole.LENDER_VIEWER, UserRole.PLATFORM_ADMIN)


class PortfolioAnalytics(BaseModel):
    scored_customers: int
    average_default_probability: float
    approval_rate: float
    pd_histogram: list[dict[str, float | int]]
    tier_distribution: dict[str, int]
    operator_concentration: list[dict[str, Any]]
    newly_bankable_customers: int
    estimated_debt_capacity_unlocked_usd: float


class NetworkEffectResponse(BaseModel):
    points: list[dict[str, float | int]]
    note: str = "Empirical: the model is retrained for each cooperative size."


@router.get(
    "/portfolio", response_model=PortfolioAnalytics, summary="Cross-operator portfolio risk"
)
async def portfolio(
    _: Principal = Depends(_lender),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> PortfolioAnalytics:
    p = await lender_portfolio(session, threshold=settings.decision_threshold)
    return PortfolioAnalytics(
        scored_customers=p.scored_customers,
        average_default_probability=p.average_default_probability,
        approval_rate=p.approval_rate,
        pd_histogram=p.pd_histogram,
        tier_distribution=p.tier_distribution,
        operator_concentration=p.operator_concentration,
        newly_bankable_customers=p.newly_bankable_customers,
        estimated_debt_capacity_unlocked_usd=p.estimated_debt_capacity_unlocked_usd,
    )


@router.get(
    "/network-effect",
    response_model=NetworkEffectResponse,
    summary="AUC vs. number of pooled operators (real retraining; cached)",
)
async def network_effect(
    request: Request,
    _: Principal = Depends(_lender),
) -> NetworkEffectResponse:
    cached: list[dict[str, float | int]] | None = getattr(request.app.state, "network_effect", None)
    if cached is None:
        # CPU-bound retraining — run off the event loop, then cache.
        points = await run_in_threadpool(
            compute_network_effect, GeneratorConfig(n_customers=1200, seed=21)
        )
        cached = [p.as_dict() for p in points]
        request.app.state.network_effect = cached
    return NetworkEffectResponse(points=cached)
