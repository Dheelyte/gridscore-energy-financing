"""Scoring service: end-to-end scoring, consent gating, audit, and the
cooperative-lift decision flip — all against a real Postgres + trained model."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    AuditLogRepository,
    CooperativeLiftRepository,
    FeatureSnapshotRepository,
    ScoreResultRepository,
)
from app.domain.enums import RiskTier, ScoreView
from app.ml.data_gen import GeneratorConfig, SyntheticGenerator
from app.ml.data_gen.generator import GeneratedPopulation
from app.ml.data_gen.persistence import SyntheticDataWriter
from app.ml.dataset import reference_date_for
from app.ml.model import ScoringModel
from app.ml.training import train
from app.services.scoring import ConsentRequiredError, ScoringService
from tests.integration.conftest import make_customer, make_operator

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def scoring_population() -> GeneratedPopulation:
    return SyntheticGenerator(GeneratorConfig(n_customers=1500, seed=7)).generate()


@pytest.fixture(scope="module")
def scoring_model(
    scoring_population: GeneratedPopulation, tmp_path_factory: pytest.TempPathFactory
) -> ScoringModel:
    uri = f"sqlite:///{tmp_path_factory.mktemp('mlruns') / 'mlflow.db'}"
    return train(scoring_population, tracking_uri=uri).model


def _service(
    session: AsyncSession, population: GeneratedPopulation, model: ScoringModel
) -> ScoringService:
    return ScoringService(session, model, reference_date=reference_date_for(population))


async def test_score_customer_returns_full_outcome_and_persists(
    session: AsyncSession,
    scoring_population: GeneratedPopulation,
    scoring_model: ScoringModel,
) -> None:
    summary = await SyntheticDataWriter(session).write(scoring_population)
    svc = _service(session, scoring_population, scoring_model)

    outcome = await svc.score_customer(
        summary.demo_customer_id, summary.operator_ids[0], view=ScoreView.POOLED
    )

    assert 300 <= outcome.energy_credit_score <= 850
    assert 0.0 <= outcome.default_probability <= 1.0
    assert isinstance(outcome.risk_tier, RiskTier)
    assert len(outcome.top_factors) == 5
    assert outcome.model_version

    # Persisted: a score result, a feature snapshot, and an audit entry.
    history = await ScoreResultRepository(session).history_for_customer(summary.demo_customer_id)
    assert len(history) == 1
    snap = await FeatureSnapshotRepository(session).latest_for_customer(
        summary.demo_customer_id, ScoreView.POOLED
    )
    assert snap is not None and "payg_repayment_rate" in snap.features_json
    assert await AuditLogRepository(session).count() >= 1


async def test_scoring_refused_without_consent(
    session: AsyncSession,
    scoring_population: GeneratedPopulation,
    scoring_model: ScoringModel,
) -> None:
    operator = await make_operator(session, name="No-Consent Energy", country="NG")
    customer = await make_customer(session, operator, identity_hash="f" * 64)
    svc = _service(session, scoring_population, scoring_model)

    with pytest.raises(ConsentRequiredError):
        await svc.score_customer(customer.id, operator.id)

    # The refusal is audited.
    audit = AuditLogRepository(session)
    rows = await audit.list(limit=10)
    assert any(r.action == "score.denied_no_consent" for r in rows)


async def test_cooperative_lift_flips_borderline_customer(
    session: AsyncSession,
    scoring_population: GeneratedPopulation,
    scoring_model: ScoringModel,
) -> None:
    """The headline regression: the seeded borderline customer is rejected on the
    solo (home-operator) view but approved on the pooled cooperative view."""
    summary = await SyntheticDataWriter(session).write(scoring_population)
    svc = _service(session, scoring_population, scoring_model)

    coop = await svc.score_cooperative(summary.demo_customer_id, summary.operator_ids[0])

    # The money shot.
    assert coop.solo.approved is False
    assert coop.pooled.approved is True
    assert coop.decision_flips is True

    # The pooled view is both lower-risk and higher-scoring.
    assert coop.pooled.default_probability < coop.solo.default_probability
    assert coop.pd_delta > 0.1
    assert coop.pooled.energy_credit_score > coop.solo.energy_credit_score
    assert coop.confidence_delta > 0

    # The lift is materialised and the action is audited.
    lift = await CooperativeLiftRepository(session).latest_for_customer(summary.demo_customer_id)
    assert lift is not None
    assert lift.solo_pd > lift.pooled_pd
    assert lift.lift_metric == pytest.approx(coop.pd_delta)
    rows = await AuditLogRepository(session).list(limit=20)
    assert any(r.action == "score.cooperative" for r in rows)
