"""Load a customer's raw signals from the database into the feature pipeline's
input shape. Shared by the scoring and enrichment services so feature inputs are
built one way only."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer
from app.db.repositories import EnrichmentSignalRepository, RepaymentEventRepository
from app.domain.enums import ProviderType
from app.ml.features import EventRecord, RawCustomerData


async def load_raw_customer_data(session: AsyncSession, customer: Customer) -> RawCustomerData:
    events = await RepaymentEventRepository(session).list_for_customer(customer.id)
    signal_rows = await EnrichmentSignalRepository(session).list_for_customer(customer.id)

    latest: dict[ProviderType, tuple[dt.datetime, dict[str, float]]] = {}
    for s in signal_rows:
        current = latest.get(s.provider_type)
        if current is None or s.captured_at > current[0]:
            latest[s.provider_type] = (s.captured_at, dict(s.payload_json))

    return RawCustomerData(
        home_operator_key=str(customer.home_operator_id),
        events=[
            EventRecord(
                operator_key=str(e.operator_id),
                due_date=e.due_date,
                paid_date=e.paid_date,
                status=e.status,
                instalment_amount=e.instalment_amount,
            )
            for e in events
        ],
        signals={pt: payload for pt, (_, payload) in latest.items()},
    )
