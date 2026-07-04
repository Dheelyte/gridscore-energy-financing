"""The scoring engine and the cooperative-lift differentiator.

``ScoringService`` turns the trained model into business outcomes:

* build a customer's feature vector from the database (solo or pooled view),
* run calibrated inference → default probability,
* map to an Energy Credit Score, a risk tier, and an approve/reject decision,
* attach SHAP "top factors",
* and — the differentiator — compute the **cooperative lift** by scoring the
  same customer under the *solo* (home-operator-only) and *pooled* (full
  cooperative) views, quantifying the PD/confidence improvement and whether the
  lending decision flips.

Every score is **consent-gated** and **audit-logged**. Persistence
(feature snapshots, score results, cooperative-lift rows, audit entries) goes
through the repository layer; the caller owns the transaction boundary.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import SCORES_COMPUTED
from app.db.models import CooperativeLift, FeatureSnapshot, ScoreResult
from app.db.repositories import (
    AuditLogRepository,
    ConsentRecordRepository,
    CooperativeLiftRepository,
    CustomerRepository,
    FeatureSnapshotRepository,
    ScoreResultRepository,
)
from app.domain.enums import ConsentScope, RiskTier, ScoreView
from app.ml.explain import ShapExplainer, TopFactor
from app.ml.features import FeatureExtractor, RawCustomerData
from app.ml.model import ScoringModel
from app.services.feature_io import load_raw_customer_data
from app.services.scoring.transform import is_approved, pd_to_score, pd_to_tier


class CustomerNotFoundError(LookupError):
    """No customer matches the given identifier."""


class ConsentRequiredError(PermissionError):
    """The customer has not granted (valid) consent to be scored."""


@dataclass
class ScoreOutcome:
    customer_id: UUID
    view: ScoreView
    default_probability: float
    energy_credit_score: int
    risk_tier: RiskTier
    approved: bool
    model_version: str
    top_factors: list[TopFactor]

    def as_dict(self) -> dict[str, object]:
        return {
            "customer_id": str(self.customer_id),
            "view": str(self.view),
            "default_probability": round(self.default_probability, 4),
            "energy_credit_score": self.energy_credit_score,
            "risk_tier": str(self.risk_tier),
            "approved": self.approved,
            "model_version": self.model_version,
            "top_factors": [f.as_dict() for f in self.top_factors],
        }


@dataclass
class CooperativeOutcome:
    customer_id: UUID
    solo: ScoreOutcome
    pooled: ScoreOutcome
    pd_delta: float  # solo_pd - pooled_pd (positive => pooled lowered risk)
    confidence_delta: float  # pooled confidence - solo confidence
    score_delta: int  # pooled_score - solo_score
    decision_flips: bool  # solo rejects but pooled approves
    lift_metric: float  # persisted headline = pd_delta
    extras: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "customer_id": str(self.customer_id),
            "solo": self.solo.as_dict(),
            "pooled": self.pooled.as_dict(),
            "pd_delta": round(self.pd_delta, 4),
            "confidence_delta": round(self.confidence_delta, 4),
            "score_delta": self.score_delta,
            "decision_flips": self.decision_flips,
            "lift_metric": round(self.lift_metric, 4),
        }


def _confidence(pd: float) -> float:
    """Sharpness of a probability: 0 at maximal uncertainty (0.5), 1 at extremes."""
    return abs(pd - 0.5) * 2.0


class ScoringService:
    def __init__(
        self,
        session: AsyncSession,
        model: ScoringModel,
        *,
        decision_threshold: float | None = None,
        reference_date: dt.date | None = None,
    ) -> None:
        self.session = session
        self.model = model
        self.threshold = decision_threshold if decision_threshold is not None else model.threshold
        self.reference_date = reference_date or dt.datetime.now(dt.UTC).date()

        self.customers = CustomerRepository(session)
        self.consents = ConsentRecordRepository(session)
        self.snapshots = FeatureSnapshotRepository(session)
        self.scores = ScoreResultRepository(session)
        self.lifts = CooperativeLiftRepository(session)
        self.audit = AuditLogRepository(session)

        self._extractor = FeatureExtractor()
        self._explainer = ShapExplainer(model)

    # -- public API -------------------------------------------------------- #
    async def score_customer(
        self,
        customer_id: UUID,
        requesting_operator_id: UUID,
        *,
        view: ScoreView = ScoreView.POOLED,
        require_consent: bool = True,
    ) -> ScoreOutcome:
        customer = await self.customers.get(customer_id)
        if customer is None:
            raise CustomerNotFoundError(str(customer_id))

        if require_consent:
            await self._require_scoring_consent(customer_id, requesting_operator_id)

        raw = await load_raw_customer_data(self.session, customer)
        outcome, features = self._score(customer_id, raw, view)
        await self._persist_score(outcome, requesting_operator_id, features)
        await self.audit.record(
            actor=f"operator:{requesting_operator_id}",
            action="score.computed",
            resource=f"customer:{customer_id}",
            metadata={
                "view": str(view),
                "pd": round(outcome.default_probability, 4),
                "score": outcome.energy_credit_score,
                "model_version": outcome.model_version,
            },
        )
        return outcome

    async def score_cooperative(
        self,
        customer_id: UUID,
        requesting_operator_id: UUID,
        *,
        require_consent: bool = True,
    ) -> CooperativeOutcome:
        """Score solo vs pooled and quantify the cooperative network effect."""
        customer = await self.customers.get(customer_id)
        if customer is None:
            raise CustomerNotFoundError(str(customer_id))
        if require_consent:
            await self._require_scoring_consent(customer_id, requesting_operator_id)

        raw = await load_raw_customer_data(self.session, customer)
        solo, solo_features = self._score(customer_id, raw, ScoreView.SOLO)
        pooled, pooled_features = self._score(customer_id, raw, ScoreView.POOLED)
        await self._persist_score(solo, requesting_operator_id, solo_features)
        await self._persist_score(pooled, requesting_operator_id, pooled_features)

        pd_delta = solo.default_probability - pooled.default_probability
        confidence_delta = _confidence(pooled.default_probability) - _confidence(
            solo.default_probability
        )
        decision_flips = (not solo.approved) and pooled.approved

        await self.lifts.add(
            CooperativeLift(
                customer_id=customer_id,
                solo_score=solo.energy_credit_score,
                pooled_score=pooled.energy_credit_score,
                solo_pd=solo.default_probability,
                pooled_pd=pooled.default_probability,
                lift_metric=pd_delta,
            )
        )
        await self.audit.record(
            actor=f"operator:{requesting_operator_id}",
            action="score.cooperative",
            resource=f"customer:{customer_id}",
            metadata={
                "solo_pd": round(solo.default_probability, 4),
                "pooled_pd": round(pooled.default_probability, 4),
                "pd_delta": round(pd_delta, 4),
                "decision_flips": decision_flips,
            },
        )
        return CooperativeOutcome(
            customer_id=customer_id,
            solo=solo,
            pooled=pooled,
            pd_delta=pd_delta,
            confidence_delta=confidence_delta,
            score_delta=pooled.energy_credit_score - solo.energy_credit_score,
            decision_flips=decision_flips,
            lift_metric=pd_delta,
        )

    # -- internals --------------------------------------------------------- #
    async def _require_scoring_consent(
        self, customer_id: UUID, requesting_operator_id: UUID
    ) -> None:
        consent = await self.consents.active_for_customer(customer_id, ConsentScope.SCORING)
        if consent is None:
            await self.audit.record(
                actor=f"operator:{requesting_operator_id}",
                action="score.denied_no_consent",
                resource=f"customer:{customer_id}",
                metadata={"scope": str(ConsentScope.SCORING)},
            )
            raise ConsentRequiredError(str(customer_id))

    def _score(
        self, customer_id: UUID, raw: RawCustomerData, view: ScoreView
    ) -> tuple[ScoreOutcome, dict[str, float]]:
        features = self._extractor.extract(raw, view, reference_date=self.reference_date)
        pd = self.model.predict_pd(features)
        SCORES_COMPUTED.labels(str(view)).inc()
        outcome = ScoreOutcome(
            customer_id=customer_id,
            view=view,
            default_probability=pd,
            energy_credit_score=pd_to_score(pd),
            risk_tier=pd_to_tier(pd),
            approved=is_approved(pd, self.threshold),
            model_version=self.model.version,
            top_factors=self._explainer.explain(features, top_k=5),
        )
        return outcome, features

    async def _persist_score(
        self,
        outcome: ScoreOutcome,
        requesting_operator_id: UUID,
        features: dict[str, float],
    ) -> None:
        await self.snapshots.add(
            FeatureSnapshot(
                customer_id=outcome.customer_id,
                computed_at=dt.datetime.now(dt.UTC),
                features_json=features,
                view=outcome.view,
            )
        )
        await self.scores.add(
            ScoreResult(
                customer_id=outcome.customer_id,
                requesting_operator_id=requesting_operator_id,
                view=outcome.view,
                energy_credit_score=outcome.energy_credit_score,
                default_probability=outcome.default_probability,
                risk_tier=outcome.risk_tier,
                model_version=outcome.model_version,
                explanation_json={
                    "top_factors": [f.as_dict() for f in outcome.top_factors],
                    "decision_threshold": self.threshold,
                    "approved": outcome.approved,
                },
            )
        )
