"""Constraints, cascade rules, and the audit-log immutability trigger."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Customer, RepaymentEvent, ScoreResult
from app.domain.enums import RepaymentStatus, RiskTier, ScoreView
from tests.integration.conftest import make_customer, make_operator

pytestmark = pytest.mark.integration


async def test_customer_identity_hash_is_unique(session: AsyncSession) -> None:
    op = await make_operator(session)
    await make_customer(session, op, identity_hash="d" * 64)
    session.add(Customer(identity_hash="d" * 64, home_operator_id=op.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_repayment_event_requires_valid_customer_fk(session: AsyncSession) -> None:
    op = await make_operator(session)
    session.add(
        RepaymentEvent(
            operator_id=op.id,
            customer_id=uuid.uuid4(),  # non-existent customer
            instalment_amount=Decimal("10.00"),
            currency="USD",
            due_date=dt.date(2024, 6, 1),
            status=RepaymentStatus.PENDING,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_score_result_check_constraints(session: AsyncSession) -> None:
    op = await make_operator(session)
    cust = await make_customer(session, op)
    # energy_credit_score must be within 300..850.
    session.add(
        ScoreResult(
            customer_id=cust.id,
            requesting_operator_id=op.id,
            view=ScoreView.POOLED,
            energy_credit_score=999,  # invalid
            default_probability=0.1,
            risk_tier=RiskTier.A,
            model_version="v0",
            explanation_json={},
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_deleting_customer_cascades_to_children(session: AsyncSession) -> None:
    op = await make_operator(session)
    cust = await make_customer(session, op)
    session.add(
        RepaymentEvent(
            operator_id=op.id,
            customer_id=cust.id,
            instalment_amount=Decimal("10.00"),
            currency="USD",
            due_date=dt.date(2024, 6, 1),
            status=RepaymentStatus.ON_TIME,
        )
    )
    await session.flush()

    await session.delete(cust)
    await session.flush()

    remaining = await session.scalar(sa.select(sa.func.count()).select_from(RepaymentEvent))
    assert remaining == 0


async def test_deleting_operator_with_customers_is_restricted(
    session: AsyncSession,
) -> None:
    op = await make_operator(session)
    await make_customer(session, op)
    await session.delete(op)
    with pytest.raises(IntegrityError):  # ON DELETE RESTRICT on customer.home_operator
        await session.flush()


async def test_audit_log_is_immutable(session: AsyncSession) -> None:
    entry = AuditLog(actor="a", action="b", resource="c", metadata_json={})
    session.add(entry)
    await session.flush()

    # The BEFORE UPDATE/DELETE trigger must reject mutation at the DB level.
    with pytest.raises(DBAPIError):
        await session.execute(
            sa.update(AuditLog).where(AuditLog.id == entry.id).values(action="tampered")
        )
        await session.flush()
