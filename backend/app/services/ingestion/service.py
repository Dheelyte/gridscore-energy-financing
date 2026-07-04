"""Batch/stream ingestion of repayment events — validated, anonymised, idempotent.

Pipeline per row:
1. **Validate** against :class:`RawRepaymentRow` (per-row errors, never abort the
   whole batch).
2. **Anonymise** the raw identifier into a salted hash (raw value discarded).
3. **Resolve** the customer (get-or-create by hash; new customers get captured
   consent records).
4. **Dedup** on ``(customer, operator, due_date)`` — re-running a batch inserts
   nothing.
5. **Persist** the repayment event.

The service reports received / inserted / duplicates / failed counts plus a
per-row error list, and the set of customers touched (so enrichment can follow)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConsentRecord, Customer, RepaymentEvent
from app.db.repositories import (
    ConsentRecordRepository,
    CustomerRepository,
    RepaymentEventRepository,
)
from app.domain.enums import ConsentScope
from app.services.ingestion.anonymise import hash_identity
from app.services.ingestion.schemas import IngestionReport, RawRepaymentRow, RowError

_DEFAULT_CONSENT = (ConsentScope.DATA_SHARING, ConsentScope.ENRICHMENT, ConsentScope.SCORING)


@dataclass
class IngestionResult:
    report: IngestionReport
    affected_customer_ids: set[UUID] = field(default_factory=set)


class IngestionService:
    def __init__(self, session: AsyncSession, *, identity_salt: str) -> None:
        self.session = session
        self.salt = identity_salt
        self.customers = CustomerRepository(session)
        self.repayments = RepaymentEventRepository(session)
        self.consents = ConsentRecordRepository(session)

    async def ingest_rows(
        self,
        rows: list[dict[str, Any]],
        operator_id: UUID,
        *,
        consent_scopes: tuple[ConsentScope, ...] = _DEFAULT_CONSENT,
    ) -> IngestionResult:
        report = IngestionReport(received=len(rows))
        affected: set[UUID] = set()
        # Caches keyed by customer id: existing due dates (loaded once per customer).
        seen_due: dict[UUID, set[dt.date]] = {}
        customer_by_hash: dict[str, Customer] = {}

        for index, raw in enumerate(rows):
            try:
                row = RawRepaymentRow.model_validate(raw)
            except ValidationError as exc:
                report.failed += 1
                report.errors.append(RowError(index=index, message=_first_error(exc)))
                continue

            identity_hash = hash_identity(row.raw_identifier, salt=self.salt)
            customer = customer_by_hash.get(identity_hash)
            if customer is None:
                customer, created = await self._resolve_customer(
                    identity_hash, operator_id, consent_scopes
                )
                customer_by_hash[identity_hash] = customer
                if created:
                    report.customers_created += 1
                seen_due[customer.id] = await self.repayments.existing_due_dates(
                    customer.id, operator_id
                )

            if row.due_date in seen_due[customer.id]:
                report.duplicates += 1
                continue

            self.session.add(
                RepaymentEvent(
                    operator_id=operator_id,
                    customer_id=customer.id,
                    instalment_amount=row.instalment_amount,
                    currency=row.currency,
                    due_date=row.due_date,
                    paid_date=row.paid_date,
                    status=row.status,
                )
            )
            seen_due[customer.id].add(row.due_date)
            report.inserted += 1
            affected.add(customer.id)

        await self.session.flush()
        return IngestionResult(report=report, affected_customer_ids=affected)

    async def _resolve_customer(
        self,
        identity_hash: str,
        operator_id: UUID,
        consent_scopes: tuple[ConsentScope, ...],
    ) -> tuple[Customer, bool]:
        existing = await self.customers.get_by_identity_hash(identity_hash)
        if existing is not None:
            return existing, False

        customer = Customer(identity_hash=identity_hash, home_operator_id=operator_id)
        self.session.add(customer)
        await self.session.flush()
        now = dt.datetime.now(dt.UTC)
        for scope in consent_scopes:
            self.session.add(
                ConsentRecord(
                    customer_id=customer.id,
                    scope=scope,
                    granted=True,
                    source="ingestion",
                    granted_at=now,
                    expires_at=now + dt.timedelta(days=730),
                )
            )
        await self.session.flush()
        return customer, True


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err.get("loc", ()))
    return f"{loc}: {err.get('msg', 'invalid')}" if loc else str(err.get("msg", "invalid"))
