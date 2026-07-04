# GridScore AI — Backend

FastAPI (async) service for the GridScore cooperative credit platform.

> **Stage 0** delivers a runnable skeleton: config, structured logging, and
> `/health` + `/ready` probes. Business logic arrives in later stages.

## Quick start (local, without Docker)

```bash
cd backend
uv venv                      # create .venv
uv pip install -e ".[dev]"   # install runtime + dev deps
uv run uvicorn app.main:app --reload --port 8000
# -> http://localhost:8000/health
# -> http://localhost:8000/docs   (OpenAPI UI)
```

## Test / lint / type-check

```bash
uv run pytest            # test suite
uv run ruff check .      # lint
uv run black --check .   # formatting
uv run mypy              # static types
```

See the repository root `README.md` for the full-stack Docker workflow.
# gridscore-energy-financing
