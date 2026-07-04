"""Integration test fixtures backed by a real PostgreSQL (testcontainers).

A single containerised Postgres is started for the test session and migrated to
head with the real Alembic migration — so these tests exercise the actual
schema, partitions, constraints, and triggers, not a ``create_all`` shortcut.

Per-test isolation uses the classic "connection-bound session inside a
transaction that is always rolled back" pattern: fast, and no truncation."""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.core.config as config_module
from app.db.models import Customer, Operator
from app.domain.enums import OperatorStatus

BACKEND_DIR = Path(__file__).resolve().parents[2]
POSTGRES_IMAGE = "postgres:16-alpine"


def _apply_migrations(database_url: str) -> None:
    """Point settings at ``database_url`` and run ``alembic upgrade head``."""
    os.environ["GRIDSCORE_DATABASE_URL"] = database_url
    config_module.get_settings.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Session-scoped migrated Postgres. Sync fixture so Alembic's
    ``asyncio.run`` is not nested inside a running test event loop."""
    from testcontainers.postgres import PostgresContainer

    previous = os.environ.get("GRIDSCORE_DATABASE_URL")
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        url = f"postgresql+asyncpg://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}"
        _apply_migrations(url)
        try:
            yield url
        finally:
            if previous is None:
                os.environ.pop("GRIDSCORE_DATABASE_URL", None)
            else:
                os.environ["GRIDSCORE_DATABASE_URL"] = previous
            config_module.get_settings.cache_clear()


@pytest_asyncio.fixture
async def session(pg_url: str) -> AsyncIterator[AsyncSession]:
    """A session wrapped in a transaction that is rolled back after the test."""
    engine = create_async_engine(pg_url)
    conn = await engine.connect()
    trans = await conn.begin()
    factory = async_sessionmaker(bind=conn, expire_on_commit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        await db.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()
        await engine.dispose()


# --------------------------------------------------------------------------- #
# Small builders so tests read clearly. They flush (not commit) so generated
# columns are populated within the test transaction.
# --------------------------------------------------------------------------- #
async def make_operator(
    session: AsyncSession, *, name: str = "Acme Solar", country: str = "KE"
) -> Operator:
    op = Operator(name=name, country=country, status=OperatorStatus.ACTIVE)
    session.add(op)
    await session.flush()
    return op


async def make_customer(
    session: AsyncSession, operator: Operator, *, identity_hash: str | None = None
) -> Customer:
    cust = Customer(
        identity_hash=identity_hash or ("a" * 64),
        home_operator_id=operator.id,
    )
    session.add(cust)
    await session.flush()
    return cust


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
