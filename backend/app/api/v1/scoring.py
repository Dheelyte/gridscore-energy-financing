"""Scoring endpoints — the B2B core. Rate-limited and tenant-isolated."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AuthorizationError, NotFoundError
from app.api.v1.deps import (
    Principal,
    ensure_customer_access,
    get_principal,
    get_scoring_model,
    get_session,
    get_settings_dep,
    rate_limit,
)
from app.api.v1.schemas import (
    CooperativeOut,
    CooperativeScoreRequest,
    ScoreOut,
    ScoreRequest,
    TopFactorOut,
)
from app.core.config import Settings
from app.db.repositories import CustomerRepository
from app.ml.model import ScoringModel
from app.services.scoring import ConsentRequiredError, CustomerNotFoundError, ScoringService
from app.services.scoring.service import CooperativeOutcome, ScoreOutcome

router = APIRouter(tags=["scoring"])

_SCORE_RATE_LIMIT = Depends(rate_limit(limit=60, window_seconds=60))


def _to_score_out(outcome: ScoreOutcome) -> ScoreOut:
    return ScoreOut(
        customer_id=outcome.customer_id,
        view=outcome.view,
        default_probability=outcome.default_probability,
        energy_credit_score=outcome.energy_credit_score,
        risk_tier=outcome.risk_tier,
        approved=outcome.approved,
        model_version=outcome.model_version,
        top_factors=[TopFactorOut(**f.as_dict()) for f in outcome.top_factors],
    )


async def _service(
    session: AsyncSession, model: ScoringModel, settings: Settings
) -> ScoringService:
    return ScoringService(session, model, decision_threshold=settings.decision_threshold)


async def _authorise_customer(
    customer_id: UUID, principal: Principal, session: AsyncSession
) -> None:
    customer = await CustomerRepository(session).get(customer_id)
    if customer is None:
        raise NotFoundError("Customer not found.")
    ensure_customer_access(principal, customer)


@router.post(
    "/score",
    response_model=ScoreOut,
    summary="Score a customer (solo or pooled view)",
    dependencies=[_SCORE_RATE_LIMIT],
)
async def score(
    body: ScoreRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    model: ScoringModel = Depends(get_scoring_model),
    settings: Settings = Depends(get_settings_dep),
) -> ScoreOut:
    await _authorise_customer(body.customer_id, principal, session)
    service = await _service(session, model, settings)
    try:
        outcome = await service.score_customer(
            body.customer_id, _operator_of(principal), view=body.view
        )
    except CustomerNotFoundError as exc:
        raise NotFoundError("Customer not found.") from exc
    except ConsentRequiredError as exc:
        raise AuthorizationError(
            "Customer has not granted consent to be scored.", details={"code": "consent_required"}
        ) from exc
    return _to_score_out(outcome)


@router.post(
    "/score/cooperative",
    response_model=CooperativeOut,
    summary="Cooperative lift: solo vs pooled, with the decision flip",
    dependencies=[_SCORE_RATE_LIMIT],
)
async def score_cooperative(
    body: CooperativeScoreRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    model: ScoringModel = Depends(get_scoring_model),
    settings: Settings = Depends(get_settings_dep),
) -> CooperativeOut:
    await _authorise_customer(body.customer_id, principal, session)
    service = await _service(session, model, settings)
    try:
        outcome: CooperativeOutcome = await service.score_cooperative(
            body.customer_id, _operator_of(principal)
        )
    except CustomerNotFoundError as exc:
        raise NotFoundError("Customer not found.") from exc
    except ConsentRequiredError as exc:
        raise AuthorizationError(
            "Customer has not granted consent to be scored.", details={"code": "consent_required"}
        ) from exc
    return CooperativeOut(
        customer_id=outcome.customer_id,
        solo=_to_score_out(outcome.solo),
        pooled=_to_score_out(outcome.pooled),
        pd_delta=outcome.pd_delta,
        confidence_delta=outcome.confidence_delta,
        score_delta=outcome.score_delta,
        decision_flips=outcome.decision_flips,
        lift_metric=outcome.lift_metric,
    )


def _operator_of(principal: Principal) -> UUID:
    """The operator on whose behalf the score is requested."""
    if principal.operator_id is None:
        raise AuthorizationError("This principal is not bound to an operator.")
    return principal.operator_id
