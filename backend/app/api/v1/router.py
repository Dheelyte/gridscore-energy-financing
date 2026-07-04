"""Aggregate all v1 routers under ``/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    customers,
    ingestion,
    operators,
    portfolio,
    scoring,
)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth.router)
v1_router.include_router(operators.router)
v1_router.include_router(customers.router)
v1_router.include_router(ingestion.router)
v1_router.include_router(scoring.router)
v1_router.include_router(portfolio.router)
v1_router.include_router(analytics.router)
v1_router.include_router(admin.router)
