"""Concrete repositories — one per aggregate, with intention-revealing queries.

Where a query encodes a domain rule (e.g. *active* consent, the *solo* view of a
customer's history) the method name says so, keeping that rule in one place."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select

from app.db.models import (
    ApiCredential,
    AuditLog,
    ConsentRecord,
    CooperativeLift,
    Customer,
    EnrichmentSignal,
    FeatureSnapshot,
    ModelVersion,
    Operator,
    RepaymentEvent,
    ScoreResult,
    UserAccount,
)
from app.db.repositories.base import BaseRepository
from app.domain.enums import ConsentScope, PromotionStage, ScoreView


class OperatorRepository(BaseRepository[Operator]):
    model = Operator

    async def get_by_name(self, name: str) -> Operator | None:
        return await self._scalar_one_or_none(select(Operator).where(Operator.name == name))


class UserAccountRepository(BaseRepository[UserAccount]):
    model = UserAccount

    async def get_by_email(self, email: str) -> UserAccount | None:
        return await self._scalar_one_or_none(select(UserAccount).where(UserAccount.email == email))


class ApiCredentialRepository(BaseRepository[ApiCredential]):
    model = ApiCredential

    async def get_by_prefix(self, key_prefix: str) -> ApiCredential | None:
        return await self._scalar_one_or_none(
            select(ApiCredential).where(ApiCredential.key_prefix == key_prefix)
        )


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def get_by_identity_hash(self, identity_hash: str) -> Customer | None:
        return await self._scalar_one_or_none(
            select(Customer).where(Customer.identity_hash == identity_hash)
        )

    async def list_for_operator(self, operator_id: UUID) -> list[Customer]:
        result = await self.session.scalars(
            select(Customer).where(Customer.home_operator_id == operator_id)
        )
        return list(result.all())


class ConsentRecordRepository(BaseRepository[ConsentRecord]):
    model = ConsentRecord

    async def active_for_customer(
        self,
        customer_id: UUID,
        scope: ConsentScope,
        *,
        at: dt.datetime | None = None,
    ) -> ConsentRecord | None:
        """The current granted, unexpired consent for a scope (most recent)."""
        now = at or dt.datetime.now(dt.UTC)
        stmt = (
            select(ConsentRecord)
            .where(
                ConsentRecord.customer_id == customer_id,
                ConsentRecord.scope == scope,
                ConsentRecord.granted.is_(True),
                ConsentRecord.granted_at <= now,
                (ConsentRecord.expires_at.is_(None)) | (ConsentRecord.expires_at > now),
            )
            .order_by(ConsentRecord.granted_at.desc())
            .limit(1)
        )
        return await self._scalar_one_or_none(stmt)


class RepaymentEventRepository(BaseRepository[RepaymentEvent]):
    model = RepaymentEvent

    async def existing_due_dates(self, customer_id: UUID, operator_id: UUID) -> set[dt.date]:
        """Due dates already recorded for a customer at an operator — the natural
        idempotency key for ingestion (one instalment per customer/operator/month)."""
        result = await self.session.scalars(
            select(RepaymentEvent.due_date).where(
                RepaymentEvent.customer_id == customer_id,
                RepaymentEvent.operator_id == operator_id,
            )
        )
        return set(result.all())

    async def list_for_customer(self, customer_id: UUID) -> list[RepaymentEvent]:
        """The **pooled** view: a customer's full cooperative history."""
        result = await self.session.scalars(
            select(RepaymentEvent)
            .where(RepaymentEvent.customer_id == customer_id)
            .order_by(RepaymentEvent.due_date)
        )
        return list(result.all())

    async def list_for_customer_solo(
        self, customer_id: UUID, operator_id: UUID
    ) -> list[RepaymentEvent]:
        """The **solo** view: only the history visible to one operator."""
        result = await self.session.scalars(
            select(RepaymentEvent)
            .where(
                RepaymentEvent.customer_id == customer_id,
                RepaymentEvent.operator_id == operator_id,
            )
            .order_by(RepaymentEvent.due_date)
        )
        return list(result.all())


class EnrichmentSignalRepository(BaseRepository[EnrichmentSignal]):
    model = EnrichmentSignal

    async def list_for_customer(self, customer_id: UUID) -> list[EnrichmentSignal]:
        result = await self.session.scalars(
            select(EnrichmentSignal).where(EnrichmentSignal.customer_id == customer_id)
        )
        return list(result.all())


class FeatureSnapshotRepository(BaseRepository[FeatureSnapshot]):
    model = FeatureSnapshot

    async def latest_for_customer(
        self, customer_id: UUID, view: ScoreView
    ) -> FeatureSnapshot | None:
        return await self._scalar_one_or_none(
            select(FeatureSnapshot)
            .where(
                FeatureSnapshot.customer_id == customer_id,
                FeatureSnapshot.view == view,
            )
            .order_by(FeatureSnapshot.computed_at.desc())
            .limit(1)
        )


class ScoreResultRepository(BaseRepository[ScoreResult]):
    model = ScoreResult

    async def history_for_customer(
        self, customer_id: UUID, *, limit: int = 50
    ) -> list[ScoreResult]:
        result = await self.session.scalars(
            select(ScoreResult)
            .where(ScoreResult.customer_id == customer_id)
            .order_by(ScoreResult.created_at.desc())
            .limit(limit)
        )
        return list(result.all())


class CooperativeLiftRepository(BaseRepository[CooperativeLift]):
    model = CooperativeLift

    async def latest_for_customer(self, customer_id: UUID) -> CooperativeLift | None:
        return await self._scalar_one_or_none(
            select(CooperativeLift)
            .where(CooperativeLift.customer_id == customer_id)
            .order_by(CooperativeLift.created_at.desc())
            .limit(1)
        )


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def record(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        metadata: dict[str, object] | None = None,
    ) -> AuditLog:
        """Append an immutable audit entry."""
        entry = AuditLog(
            actor=actor, action=action, resource=resource, metadata_json=metadata or {}
        )
        return await self.add(entry)


class ModelVersionRepository(BaseRepository[ModelVersion]):
    model = ModelVersion

    async def get_by_version(self, version: str) -> ModelVersion | None:
        return await self._scalar_one_or_none(
            select(ModelVersion).where(ModelVersion.version == version)
        )

    async def get_production(self) -> ModelVersion | None:
        return await self._scalar_one_or_none(
            select(ModelVersion)
            .where(ModelVersion.promoted_stage == PromotionStage.PRODUCTION)
            .order_by(ModelVersion.created_at.desc())
            .limit(1)
        )
