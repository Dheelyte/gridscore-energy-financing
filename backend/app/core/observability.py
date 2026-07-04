"""Observability: Prometheus metrics, request correlation IDs, structured request
logs, and OpenTelemetry tracing (console exporter in dev).

A single ASGI middleware binds a ``request_id`` to the structlog context, opens
an OpenTelemetry span, records Prometheus request metrics, and emits one
structured access log per request. ``/metrics`` exposes the Prometheus registry.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings
from app.core.logging import get_logger

REQUEST_COUNT = Counter(
    "gridscore_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "gridscore_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
SCORES_COMPUTED = Counter(
    "gridscore_scores_computed_total",
    "Scores computed",
    ["view"],
)

_log = get_logger("app.access")
_tracer = trace.get_tracer("gridscore")


def configure_tracing(settings: Settings) -> None:
    """Install a tracer provider with a console span exporter (dev-friendly).

    Idempotent: only sets the global provider once."""
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return
    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": "gridscore-api", "deployment.environment": str(settings.env)}
        )
    )
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


def _route_template(request: Request) -> str:
    """Low-cardinality path label: the route template, not the raw path."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        import structlog

        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()

        with _tracer.start_as_current_span(f"{request.method} {request.url.path}") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.target", request.url.path)
            span.set_attribute("gridscore.request_id", request_id)
            try:
                response = await call_next(request)
            finally:
                pass
            span.set_attribute("http.status_code", response.status_code)

        duration = time.perf_counter() - start
        path = _route_template(request)
        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(duration)
        response.headers["X-Request-ID"] = request_id
        _log.info(
            "request",
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        structlog.contextvars.unbind_contextvars("request_id")
        return response


def register_observability(app: FastAPI, settings: Settings) -> None:
    configure_tracing(settings)
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
