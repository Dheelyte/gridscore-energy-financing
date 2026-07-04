"""Structured logging via structlog.

In development we render colourised, human-friendly console logs. In
staging/production we emit single-line JSON so logs are machine-parseable by
the platform's log aggregator. A ``request_id`` correlation field is bound by
the API middleware (added in Stage 5/9); the pipeline is set up here so every
log line is consistent from Stage 0 onward.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging + structlog according to settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through structlog.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: structlog.typing.Processor
    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
        shared_processors.append(structlog.processors.format_exc_info)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
