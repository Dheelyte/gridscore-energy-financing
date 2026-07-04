"""Customer lookup, consent, and score history — strictly tenant-scoped."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import NotFoundError
from app.api.v1.deps import Principal, ensure_customer_access, get_principal, get_session
from app.api.v1.schemas import ConsentCreate, ConsentOut, CustomerOut, ScoreHistoryItem
from app.db.models import ConsentRecord, Customer, ScoreResult
from app.db.repositories import (
    ConsentRecordRepository,
    CustomerRepository,
    ScoreResultRepository,
)

router = APIRouter(prefix="/customers", tags=["customers"])


async def _load_owned_customer(
    customer_id: UUID, principal: Principal, session: AsyncSession
) -> Customer:
    customer = await CustomerRepository(session).get(customer_id)
    if customer is None:
        raise NotFoundError("Customer not found.")
    ensure_customer_access(principal, customer)
    return customer


@router.get("", response_model=list[CustomerOut], summary="List this operator's customers")
async def list_customers(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Customer]:
    repo = CustomerRepository(session)
    if principal.is_platform_admin:
        return await repo.list(limit=200)
    if principal.operator_id is None:
        return []
    return await repo.list_for_operator(principal.operator_id)


@router.get("/{customer_id}", response_model=CustomerOut, summary="Get a customer")
async def get_customer(
    customer_id: UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Customer:
    return await _load_owned_customer(customer_id, principal, session)


@router.get(
    "/{customer_id}/consents",
    response_model=list[ConsentOut],
    summary="List a customer's consent records",
)
async def list_consents(
    customer_id: UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ConsentRecord]:
    await _load_owned_customer(customer_id, principal, session)
    repo = ConsentRecordRepository(session)
    rows = await repo.list(limit=100)
    return [c for c in rows if c.customer_id == customer_id]


@router.post(
    "/{customer_id}/consents",
    response_model=ConsentOut,
    status_code=201,
    summary="Record a consent grant/denial",
)
async def create_consent(
    customer_id: UUID,
    body: ConsentCreate,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ConsentRecord:
    await _load_owned_customer(customer_id, principal, session)
    return await ConsentRecordRepository(session).add(
        ConsentRecord(
            customer_id=customer_id,
            scope=body.scope,
            granted=body.granted,
            source=body.source,
            granted_at=dt.datetime.now(dt.UTC),
            expires_at=body.expires_at,
        )
    )


@router.get(
    "/{customer_id}/scores",
    response_model=list[ScoreHistoryItem],
    summary="Score history for a customer",
)
async def score_history(
    customer_id: UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ScoreResult]:
    await _load_owned_customer(customer_id, principal, session)
    return await ScoreResultRepository(session).history_for_customer(customer_id)
