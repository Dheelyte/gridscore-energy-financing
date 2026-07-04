"""Generic async repository.

Repositories are the only place the rest of the app issues queries. Services
depend on repositories, never on the ``AsyncSession`` directly, which keeps
persistence concerns in one layer and makes the data access testable and
swappable. Transaction control (commit/rollback) belongs to the caller/session
scope (see ``app.db.session.get_session``), not the repository."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD building blocks shared by all repositories."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, instance: ModelT) -> ModelT:
        """Persist a new instance and populate DB-generated columns."""
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get(self, id_: UUID) -> ModelT | None:
        """Fetch by single-column UUID primary key."""
        return await self.session.get(self.model, id_)

    async def _scalar_one_or_none(self, stmt: Select[tuple[ModelT]]) -> ModelT | None:
        """Run a single-entity SELECT. Restores the precise return type that
        SQLAlchemy's ``scalar`` erases to ``Any``."""
        row: ModelT | None = await self.session.scalar(stmt)
        return row

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self.session.scalars(select(self.model).limit(limit).offset(offset))
        return list(result.all())

    async def count(self) -> int:
        result = await self.session.scalar(select(func.count()).select_from(self.model))
        return int(result or 0)

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()
