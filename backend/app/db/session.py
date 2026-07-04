"""Async database engine and session management.

The engine and session factory are created once per application (in the app
factory) and stored on ``app.state``. Request handlers receive a session via the
``get_session`` FastAPI dependency, which guarantees commit/rollback/close
semantics. Nothing outside this module talks to the engine directly."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine. Connections are opened lazily on first use."""
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,  # transparently recycle stale connections
        future=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session.

    Commits on success, rolls back on exception, always closes."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.db_sessionmaker
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
