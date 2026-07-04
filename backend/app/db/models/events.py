"""Cooperative signal models: repayment events (partitioned) and enrichment."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, pg_enum
from app.db.types import uuid7
from app.domain.enums import ProviderType, RepaymentStatus

if TYPE_CHECKING:
    from app.db.models.customer import Customer
    from app.db.models.tenancy import Operator


class RepaymentEvent(Base):
    """A single PAYG instalment outcome — the cooperative's raw signal.

    The table is **range-partitioned by month** on ``due_date`` (declared via
    ``postgresql_partition_by``). PostgreSQL requires the partition key to be
    part of every unique constraint, so the primary key is the composite
    ``(id, due_date)``. Monthly child partitions are created in the migration.
    """

    __tablename__ = "repayment_event"
    __table_args__ = (
        Index("ix_repayment_event_customer_id_due_date", "customer_id", "due_date"),
        Index("ix_repayment_event_operator_id", "operator_id"),
        Index("ix_repayment_event_status", "status"),
        {"postgresql_partition_by": "RANGE (due_date)"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    due_date: Mapped[dt.date] = mapped_column(Date, primary_key=True, nullable=False)

    operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("operator.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False
    )
    instalment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    paid_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[RepaymentStatus] = mapped_column(
        pg_enum(RepaymentStatus, "repayment_status"),
        default=RepaymentStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    operator: Mapped[Operator] = relationship(back_populates="repayment_events")
    customer: Mapped[Customer] = relationship(back_populates="repayment_events")


class EnrichmentSignal(Base):
    """An external signal (mobile-money, airtime, utility) captured for a
    customer via a provider adapter. Payload kept as JSONB for adapter freedom."""

    __tablename__ = "enrichment_signal"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        pg_enum(ProviderType, "provider_type"), nullable=False
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="enrichment_signals")
