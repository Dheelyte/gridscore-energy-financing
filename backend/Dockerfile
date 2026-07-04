# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# GridScore backend image — multi-stage, uv-based.
# Stage `builder` resolves deps into a venv; `runtime` is a slim final image
# running as a non-root user.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# uv: fast, reproducible Python dependency resolution.
COPY --from=ghcr.io/astral-sh/uv:0.9.15 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Copy only dependency metadata first for layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN uv venv /opt/venv && uv pip install --python /opt/venv -e .

# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
# alembic.ini is needed so `alembic upgrade head` can run at deploy time;
# artifacts/ carries the trained scoring model the API loads at startup.
COPY alembic.ini pyproject.toml README.md ./
COPY artifacts ./artifacts

USER appuser
EXPOSE 8000

# Container-level liveness check.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
