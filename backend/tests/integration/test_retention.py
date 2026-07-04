"""Data-retention purge: old derived artefacts are deleted, recent ones kept."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CooperativeLift, FeatureSnapshot, ScoreResult
from app.domain.enums import RiskTier, ScoreView
from app.services.retention import purge_derived_data
from tests.integration.conftest import make_customer, make_operator

pytestmark = pytest.mark.integration


async def test_purge_removes_only_old_derived_rows(session: AsyncSession) -> None:
    op = await make_operator(session)
    cust = await make_customer(session, op)
    now = dt.datetime.now(dt.UTC)
    old = now - dt.timedelta(days=400)

    def snapshot(when: dt.datetime) -> FeatureSnapshot:
        return FeatureSnapshot(
            customer_id=cust.id,
            computed_at=when,
            features_json={},
            view=ScoreView.POOLED,
            created_at=when,
        )

    def score(when: dt.datetime) -> ScoreResult:
        return ScoreResult(
            customer_id=cust.id,
            requesting_operator_id=op.id,
            view=ScoreView.POOLED,
            energy_credit_score=600,
            default_probability=0.1,
            risk_tier=RiskTier.C,
            model_version="v1",
            explanation_json={},
            created_at=when,
        )

    def lift(when: dt.datetime) -> CooperativeLift:
        return CooperativeLift(
            customer_id=cust.id,
            solo_score=500,
            pooled_score=650,
            solo_pd=0.3,
            pooled_pd=0.1,
            lift_metric=0.2,
            created_at=when,
        )

    session.add_all([snapshot(old), snapshot(now), score(old), score(now), lift(old), lift(now)])
    await session.flush()

    result = await purge_derived_data(session, retention_days=365)

    assert result.feature_snapshots == 1
    assert result.score_results == 1
    assert result.cooperative_lifts == 1
    assert result.total == 3

    # Exactly the recent rows survive.
    for model in (FeatureSnapshot, ScoreResult, CooperativeLift):
        remaining = await session.scalar(sa.select(sa.func.count()).select_from(model))
        assert remaining == 1
