"""Tenancy & access models: operators, human users, machine API credentials."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.domain.enums import OperatorStatus, UserRole, UserStatus

if TYPE_CHECKING:
    from app.db.models.customer import Customer
    from app.db.models.events import RepaymentEvent


class Operator(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A PAYG energy company — the tenant of the system."""

    __tablename__ = "operator"

    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    status: Mapped[OperatorStatus] = mapped_column(
        pg_enum(OperatorStatus, "operator_status"),
        default=OperatorStatus.PENDING,
        nullable=False,
    )

    users: Mapped[list[UserAccount]] = relationship(
        back_populates="operator", cascade="all, delete-orphan", passive_deletes=True
    )
    api_credentials: Mapped[list[ApiCredential]] = relationship(
        back_populates="operator", cascade="all, delete-orphan", passive_deletes=True
    )
    # Customers and events are RESTRICT at the DB level — an operator with data
    # cannot be deleted. passive_deletes lets that DB rule fire instead of the
    # ORM attempting to null a NOT NULL column first.
    customers: Mapped[list[Customer]] = relationship(
        back_populates="home_operator",
        foreign_keys="Customer.home_operator_id",
        passive_deletes="all",
    )
    repayment_events: Mapped[list[RepaymentEvent]] = relationship(
        back_populates="operator",
        passive_deletes="all",
    )


class UserAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A human user. RBAC subject. ``operator_id`` is null for platform/lender
    users who do not belong to a single tenant."""

    __tablename__ = "user_account"

    operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("operator.id", ondelete="CASCADE"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status"),
        default=UserStatus.INVITED,
        nullable=False,
    )

    operator: Mapped[Operator | None] = relationship(back_populates="users")


class ApiCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Machine-to-machine credential for an operator. Only the *hash* of the
    secret is stored; the plaintext is shown once at creation (Stage 5)."""

    __tablename__ = "api_credential"

    operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("operator.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Public, indexed lookup handle (e.g. "gsk_live_AB12CD"); the secret follows.
    key_prefix: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    hashed_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]")
    )
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    operator: Mapped[Operator] = relationship(back_populates="api_credentials")
