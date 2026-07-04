"""Shared pytest fixtures for unit tests (no external infrastructure).

Integration fixtures that stand up a real Postgres live in
``tests/integration/conftest.py``."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Environment, Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Isolated settings for tests (never reads a developer's real .env)."""
    return Settings(env=Environment.DEVELOPMENT, log_json=False, _env_file=None)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """A fresh app instance with overridable dependencies."""
    return create_app(settings)


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the ASGI app in-process (no network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
