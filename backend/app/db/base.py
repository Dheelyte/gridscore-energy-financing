"""SQLAlchemy declarative base, naming conventions, and shared mixins."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import uuid7

_E = TypeVar("_E", bound=StrEnum)


def pg_enum(enum_cls: type[_E], name: str) -> Enum:
    """Native PostgreSQL ENUM that stores the StrEnum *values* (lowercase),
    not the Python member names.

    The ENUM types are metadata-bound: ``create_all``/``drop_all`` create and
    drop them for the whole metadata (the initial migration relies on this), so
    type lifecycle stays in lock-step with the models.
    """
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [member.value for member in e],
    )


# Deterministic constraint/index names so Alembic migrations are stable and
# autogenerate diffs stay clean (Postgres otherwise invents names).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Time-ordered UUIDv7 primary key, generated application-side."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)


class TimestampMixin:
    """``created_at`` set by the database on insert (authoritative server time)."""

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
