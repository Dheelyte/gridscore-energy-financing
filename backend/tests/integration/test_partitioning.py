"""Monthly partition routing for repayment_event."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RepaymentEvent
from app.domain.enums import RepaymentStatus
from tests.integration.conftest import make_customer, make_operator

pytestmark = pytest.mark.integration


async def _insert(session: AsyncSession, due_date: dt.date) -> None:
    op = await make_operator(session, name=f"Op-{due_date}", country="KE")
    cust = await make_customer(session, op, identity_hash=str(due_date).ljust(64, "0"))
    session.add(
        RepaymentEvent(
            operator_id=op.id,
            customer_id=cust.id,
            instalment_amount=Decimal("10.00"),
            currency="USD",
            due_date=due_date,
            status=RepaymentStatus.ON_TIME,
        )
    )
    await session.flush()


async def _partition_of(session: AsyncSession, due_date: dt.date) -> str:
    row = await session.execute(
        sa.text(
            "SELECT tableoid::regclass::text AS part FROM repayment_event " "WHERE due_date = :d"
        ),
        {"d": due_date},
    )
    return str(row.scalar_one())


async def test_event_routes_to_correct_monthly_partition(session: AsyncSession) -> None:
    in_window = dt.date(2024, 5, 15)
    await _insert(session, in_window)
    assert await _partition_of(session, in_window) == "repayment_event_2024_05"


async def test_event_outside_window_lands_in_default_partition(
    session: AsyncSession,
) -> None:
    out_of_window = dt.date(2099, 1, 1)
    await _insert(session, out_of_window)
    assert await _partition_of(session, out_of_window) == "repayment_event_default"
