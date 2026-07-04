"""GridScore AI API — application factory and ASGI entrypoint.

Run locally with:
    uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.v1.router import v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.observability import register_observability
from app.db.redis import create_redis
from app.db.session import create_engine, create_session_factory
from app.services.scoring import ModelNotTrainedError, load_scoring_model
from app.workers.queue import create_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: load the scoring model and dispose pooled resources.
    The engine, session factory, and Redis client are created in ``create_app``
    so they are available even when the lifespan is not run (e.g. some test
    transports)."""
    settings: Settings = app.state.settings
    log = get_logger("app.lifespan")
    try:
        app.state.scoring_model = load_scoring_model(settings.model_path)
        log.info("model_loaded", version=app.state.scoring_model.version)
    except ModelNotTrainedError:
        app.state.scoring_model = None
        log.warning("model_not_loaded", path=settings.model_path)

    # arq pool for enqueuing background ingestion jobs (best-effort).
    try:
        app.state.arq_pool = await create_arq_pool(settings)
        log.info("arq_pool_connected")
    except Exception as exc:  # pragma: no cover - depends on Redis availability
        app.state.arq_pool = None
        log.warning("arq_pool_unavailable", error=str(exc))

    log.info("startup", env=str(settings.env), version=__version__)
    yield
    if app.state.arq_pool is not None:
        await app.state.arq_pool.aclose()
    await app.state.db_engine.dispose()
    await app.state.redis.aclose()
    log.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Keeping construction in a function makes the app
    trivial to instantiate inside tests with overridden settings."""
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="GridScore AI API",
        version=__version__,
        summary="Credit infrastructure for Africa's energy lenders.",
        description=(
            "Cooperative PAYG repayment data platform. **All data in "
            "non-production environments is synthetic.**"
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.scoring_model = None  # populated by the lifespan (or tests)
    app.state.arq_pool = None  # populated by the lifespan if Redis is reachable

    # Shared resources, created once per app and stored on state.
    engine = create_engine(settings)
    app.state.db_engine = engine
    app.state.db_sessionmaker = create_session_factory(engine)
    app.state.redis = create_redis(settings)

    register_exception_handlers(app)
    register_observability(app, settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(v1_router)

    @app.get("/", tags=["meta"], summary="Service banner")
    async def root() -> dict[str, str]:
        return {
            "service": "gridscore-api",
            "version": __version__,
            "docs": "/docs",
            "note": "Synthetic data only outside production.",
        }

    return app


app = create_app()
