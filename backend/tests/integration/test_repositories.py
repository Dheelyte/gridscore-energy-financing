"""Repository CRUD and intention-revealing query tests."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConsentRecord, RepaymentEvent, UserAccount
from app.db.repositories import (
    AuditLogRepository,
    ConsentRecordRepository,
    CustomerRepository,
    OperatorRepository,
    RepaymentEventRepository,
    UserAccountRepository,
)
from app.domain.enums import ConsentScope, RepaymentStatus, UserRole, UserStatus
from tests.integration.conftest import make_customer, make_operator, utcnow

pytestmark = pytest.mark.integration


async def test_operator_crud_and_lookup(session: AsyncSession) -> None:
    repo = OperatorRepository(session)
    op = await make_operator(session, name="SunKing", country="UG")

    # created_at populated by the DB; UUIDv7 primary key generated app-side.
    assert op.created_at is not None
    assert op.id is not None

    fetched = await repo.get(op.id)
    assert fetched is not None and fetched.name == "SunKing"
    assert await repo.get_by_name("SunKing") is not None
    assert await repo.count() == 1


async def test_customer_get_by_identity_hash(session: AsyncSession) -> None:
    repo = CustomerRepository(session)
    op = await make_operator(session)
    cust = await make_customer(session, op, identity_hash="b" * 64)

    found = await repo.get_by_identity_hash("b" * 64)
    assert found is not None and found.id == cust.id
    assert await repo.get_by_identity_hash("c" * 64) is None

    for_op = await repo.list_for_operator(op.id)
    assert [c.id for c in for_op] == [cust.id]


async def test_user_account_get_by_email(session: AsyncSession) -> None:
    repo = UserAccountRepository(session)
    op = await make_operator(session)
    user = UserAccount(
        operator_id=op.id,
        email="analyst@sunking.example",
        hashed_password="x",
        role=UserRole.OPERATOR_ANALYST,
        status=UserStatus.ACTIVE,
    )
    await repo.add(user)

    assert (await repo.get_by_email("analyst@sunking.example")) is not None
    assert (await repo.get_by_email("nobody@example.com")) is None


async def test_consent_active_for_customer_respects_expiry_and_grant(
    session: AsyncSession,
) -> None:
    repo = ConsentRecordRepository(session)
    op = await make_operator(session)
    cust = await make_customer(session, op)
    now = utcnow()

    # Active grant.
    await repo.add(
        ConsentRecord(
            customer_id=cust.id,
            scope=ConsentScope.SCORING,
            granted=True,
            source="app",
            granted_at=now - dt.timedelta(days=1),
            expires_at=now + dt.timedelta(days=30),
        )
    )
    # Expired grant for a different scope.
    await repo.add(
        ConsentRecord(
            customer_id=cust.id,
            scope=ConsentScope.ENRICHMENT,
            granted=True,
            source="app",
            granted_at=now - dt.timedelta(days=400),
            expires_at=now - dt.timedelta(days=1),
        )
    )

    assert await repo.active_for_customer(cust.id, ConsentScope.SCORING) is not None
    assert await repo.active_for_customer(cust.id, ConsentScope.ENRICHMENT) is None
    assert await repo.active_for_customer(cust.id, ConsentScope.DATA_SHARING) is None


async def test_repayment_event_solo_vs_pooled_views(session: AsyncSession) -> None:
    """The solo view is one operator's slice; the pooled view is the union —
    the seed of the cooperative network effect."""
    repo = RepaymentEventRepository(session)
    home = await make_operator(session, name="Home Op", country="KE")
    other = await make_operator(session, name="Other Op", country="KE")
    cust = await make_customer(session, home)

    def event(operator_id: object, month: int) -> RepaymentEvent:
        return RepaymentEvent(
            operator_id=operator_id,
            customer_id=cust.id,
            instalment_amount=Decimal("12.50"),
            currency="USD",
            due_date=dt.date(2024, month, 15),
            paid_date=dt.date(2024, month, 14),
            status=RepaymentStatus.ON_TIME,
        )

    await repo.add(event(home.id, 1))
    await repo.add(event(home.id, 2))
    await repo.add(event(other.id, 3))  # only visible in the pooled view

    pooled = await repo.list_for_customer(cust.id)
    solo = await repo.list_for_customer_solo(cust.id, home.id)
    assert len(pooled) == 3
    assert len(solo) == 2
    assert all(e.operator_id == home.id for e in solo)


async def test_audit_log_record_appends(session: AsyncSession) -> None:
    repo = AuditLogRepository(session)
    entry = await repo.record(
        actor="user:123",
        action="score.read",
        resource="customer:abc",
        metadata={"view": "pooled"},
    )
    assert entry.id is not None
    assert entry.metadata_json == {"view": "pooled"}
    assert await repo.count() == 1
