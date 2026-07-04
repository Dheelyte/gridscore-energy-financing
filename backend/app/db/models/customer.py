"""Customer identity and consent.

A customer is identified only by a salted SHA-256 hash of a national ID or phone
number, computed at the ingestion boundary. **No raw PII is ever stored.**
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.domain.enums import ConsentScope

if TYPE_CHECKING:
    from app.db.models.events import EnrichmentSignal, RepaymentEvent
    from app.db.models.scoring import CooperativeLift, FeatureSnapshot, ScoreResult
    from app.db.models.tenancy import Operator


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An end borrower. Identity is an opaque salted hash — privacy by design."""

    __tablename__ = "customer"

    # 64-char hex SHA-256 digest. Unique => one cooperative record per person,
    # which is precisely what enables the pooled view across operators.
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    home_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("operator.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    home_operator: Mapped[Operator] = relationship(
        back_populates="customers", foreign_keys=[home_operator_id]
    )
    # passive_deletes=True: rely on the database's ON DELETE CASCADE rather than
    # having the ORM load and mutate child rows. Essential for repayment_events,
    # which can be large and is partitioned — we never want to fan it into memory
    # just to delete a customer.
    consent_records: Mapped[list[ConsentRecord]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    repayment_events: Mapped[list[RepaymentEvent]] = relationship(
        back_populates="customer", passive_deletes=True
    )
    enrichment_signals: Mapped[list[EnrichmentSignal]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    feature_snapshots: Mapped[list[FeatureSnapshot]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    score_results: Mapped[list[ScoreResult]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    cooperative_lifts: Mapped[list[CooperativeLift]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )


class ConsentRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A consent grant/denial that gates enrichment and scoring."""

    __tablename__ = "consent_record"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[ConsentScope] = mapped_column(
        pg_enum(ConsentScope, "consent_scope"), nullable=False
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)  # ussd | app | paper | api
    granted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="consent_records")
