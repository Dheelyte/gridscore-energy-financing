"""Liveness and readiness probes.

``/health``  — *liveness*: the process is up. Used to decide whether to restart.
``/ready``   — *readiness*: the process **and its critical dependencies**
               (Postgres, Redis) are ready to receive traffic. Returns HTTP 503
               when any dependency is unavailable so orchestrators stop routing.

The two dependency checks are FastAPI dependencies so they can be overridden in
unit tests without standing up real infrastructure.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger("app.health")

_CHECK_TIMEOUT_S = 2.0


class HealthState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class HealthResponse(BaseModel):
    status: HealthState = Field(description="Overall liveness status.")
    service: str = Field(description="Service identifier.")
    version: str = Field(description="Running application version.")
    environment: str = Field(description="Active deployment environment.")


class ReadinessResponse(BaseModel):
    status: HealthState = Field(description="Overall readiness status.")
    dependencies: dict[str, HealthState] = Field(
        default_factory=dict, description="Per-dependency readiness."
    )


async def check_database(request: Request) -> HealthState:
    """Readiness of Postgres: a bounded ``SELECT 1``."""
    engine: AsyncEngine = request.app.state.db_engine
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_S):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return HealthState.OK
    except Exception as exc:  # pragma: no cover - exercised via integration
        log.warning("readiness_db_failed", error=str(exc))
        return HealthState.DEGRADED


async def check_redis(request: Request) -> HealthState:
    """Readiness of Redis: a bounded ``PING``."""
    client: Redis = request.app.state.redis
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_S):
            await client.ping()
        return HealthState.OK
    except Exception as exc:  # pragma: no cover - exercised via integration
        log.warning("readiness_redis_failed", error=str(exc))
        return HealthState.DEGRADED


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status=HealthState.OK,
        service="gridscore-api",
        version=__version__,
        environment=str(settings.env),
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready(
    response: Response,
    database: HealthState = Depends(check_database),
    redis: HealthState = Depends(check_redis),
) -> ReadinessResponse:
    dependencies = {"database": database, "redis": redis}
    overall = (
        HealthState.DEGRADED
        if any(state is HealthState.DEGRADED for state in dependencies.values())
        else HealthState.OK
    )
    if overall is HealthState.DEGRADED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status=overall, dependencies=dependencies)
