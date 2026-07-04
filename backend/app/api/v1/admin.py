"""Platform-admin console: cooperative health, audit search, and the active model."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ServiceUnavailableError
from app.api.v1.deps import Principal, get_session, require_roles
from app.domain.enums import UserRole
from app.ml.model import ScoringModel
from app.services.analytics.cooperative import audit_search, cooperative_health

router = APIRouter(prefix="/admin", tags=["admin"])

_admin = require_roles(UserRole.PLATFORM_ADMIN)


class Health(BaseModel):
    operators: int
    customers: int
    repayment_events: int
    enrichment_signals: int
    scored_customers: int
    active_consents: int
    cooperative_lifts: int


class AuditEntry(BaseModel):
    actor: str
    action: str
    resource: str
    metadata: dict[str, Any]
    created_at: dt.datetime


class ActiveModel(BaseModel):
    version: str
    threshold: float
    metrics: dict[str, float]
    mlflow_run_id: str | None
    created_at: dt.datetime


@router.get("/health", response_model=Health, summary="Cooperative health")
async def health(
    _: Principal = Depends(_admin),
    session: AsyncSession = Depends(get_session),
) -> Health:
    h = await cooperative_health(session)
    return Health(**h.__dict__)


@router.get("/audit", response_model=list[AuditEntry], summary="Search the audit log")
async def audit(
    actor: str | None = None,
    action: str | None = None,
    limit: int = 50,
    _: Principal = Depends(_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEntry]:
    rows = await audit_search(session, actor=actor, action=action, limit=min(limit, 200))
    return [
        AuditEntry(
            actor=r.actor,
            action=r.action,
            resource=r.resource,
            metadata=r.metadata_json,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/model", response_model=ActiveModel, summary="The active scoring model")
async def active_model(
    request: Request,
    _: Principal = Depends(_admin),
) -> ActiveModel:
    model: ScoringModel | None = getattr(request.app.state, "scoring_model", None)
    if model is None:
        raise ServiceUnavailableError("No scoring model is loaded.")
    return ActiveModel(
        version=model.version,
        threshold=model.threshold,
        metrics=model.metrics,
        mlflow_run_id=model.mlflow_run_id,
        created_at=model.created_at,
    )
