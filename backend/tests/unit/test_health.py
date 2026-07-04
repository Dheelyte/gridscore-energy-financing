"""Smoke tests for the Stage 0 skeleton: health probes and config.

These are intentionally minimal — Stage 0 has no business logic — but they
prove the app boots, settings load, and the probes respond as documented.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.health import HealthState, check_database, check_redis
from app.core.config import Environment, Settings


@pytest.mark.unit
async def test_health_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "gridscore-api"
    assert body["environment"] == "development"


@pytest.mark.unit
async def test_ready_ok_when_dependencies_healthy(app: FastAPI, client: AsyncClient) -> None:
    # Override the dependency checks so no real infra is needed.
    app.dependency_overrides[check_database] = lambda: HealthState.OK
    app.dependency_overrides[check_redis] = lambda: HealthState.OK
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["dependencies"] == {"database": "ok", "redis": "ok"}


@pytest.mark.unit
async def test_ready_degraded_returns_503(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[check_database] = lambda: HealthState.DEGRADED
    app.dependency_overrides[check_redis] = lambda: HealthState.OK
    resp = await client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["database"] == "degraded"


@pytest.mark.unit
async def test_root_banner(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "gridscore-api"


@pytest.mark.unit
def test_cors_origins_accept_csv_string() -> None:
    """CORS origins may be provided as a comma-separated env string."""
    s = Settings(cors_origins="http://a.com, http://b.com", _env_file=None)
    assert s.cors_origins == ["http://a.com", "http://b.com"]


@pytest.mark.unit
def test_secret_not_in_repr() -> None:
    """Secrets must never leak via repr/str."""
    s = Settings(secret_key="super-secret-value", _env_file=None)
    assert "super-secret-value" not in repr(s)
    assert s.secret_key.get_secret_value() == "super-secret-value"


@pytest.mark.unit
def test_environment_flag() -> None:
    s = Settings(env=Environment.PRODUCTION, _env_file=None)
    assert s.is_production is True
