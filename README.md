# GridScore AI

**The credit infrastructure for Africa's energy lenders.**

Across Sub-Saharan Africa, pay-as-you-go (PAYG) solar lenders extend loans
without any shared record of who repays. A borrower who defaults with one
operator can get a fresh loan from the next operator the same day, while
reliable customers are rejected for lack of a verifiable track record.

GridScore is a **shared PAYG repayment data cooperative**. Operators contribute
anonymised repayment histories through a standard interface; GridScore enriches
that data with mobile-money, airtime, and utility signals and returns an
**Energy Credit Score** and a **default probability** that is sharper than any
single operator could compute alone. The defensible core is the **cooperative
network effect**: a customer scored on one operator's partial view versus the
pooled cooperative view, where the pooled score is measurably more confident and
more accurate.

> ⚠️ **All data outside production is synthetic and clearly labelled as such.**
> Model metrics are deliberately realistic, not perfect. See
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the honesty posture.

---

## Status

This repository was built in **eleven stages (0–10)** — **all complete.**

| Stage | Title | State |
|------:|-------|-------|
| 0 | Foundation & scaffolding | ✅ complete |
| 1 | Domain & data model | ✅ complete |
| 2 | Synthetic data engine | ✅ complete |
| 3 | ML platform (features, training, registry) | ✅ complete |
| 4 | Scoring service & cooperative lift | ✅ complete |
| 5 | Multi-tenant API & auth | ✅ complete |
| 6 | Ingestion & enrichment pipeline | ✅ complete |
| 7 | Operator console (frontend) | ✅ complete |
| 8 | Lender/DFI analytics & platform admin | ✅ complete |
| 9 | Observability, hardening & security | ✅ complete |
| 10 | Deployment, docs & demo packaging | ✅ complete |

Stage reports live in [`docs/stages/`](docs/stages/). The running decision log
is [`docs/DECISIONS.md`](docs/DECISIONS.md). To deploy, see
[`docs/RUNBOOK.md`](docs/RUNBOOK.md#deployment); to present, follow the timed
[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md); deferred production work is in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Architecture at a glance

A layered, multi-tenant, ports-and-adapters system:

- **Frontend** — React + TypeScript + Vite + Tailwind/shadcn (operator console,
  lender analytics, platform admin).
- **API gateway** — FastAPI (async) + Pydantic v2; JWT + API-key auth, RBAC,
  rate limiting, versioned `/v1`.
- **Services** — scoring, ingestion, analytics, consent.
- **Domain / data** — SQLAlchemy 2.0 + Alembic on PostgreSQL 16; Redis 7 for
  cache/queues.
- **ML platform** — XGBoost + SHAP + MLflow registry, model cards, drift monitor.
- **Provider adapters** — swappable mobile-money / airtime / utility ports.

Full diagram and rationale: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Quick start

### Prerequisites
- Docker + Docker Compose (for the full stack), **or**
- Python 3.12 + [uv](https://docs.astral.sh/uv/) and Node 22 (for per-stack dev).

### 1. Configure
```bash
cp .env.example .env   # adjust if needed; safe defaults for local dev
```

### 2. Run the whole stack with Docker
```bash
docker compose -f infra/docker-compose.yml up --build
```
Then open:
- API health  → http://localhost:8000/health
- API docs    → http://localhost:8000/docs
- Frontend    → http://localhost:8080
- MLflow      → http://localhost:5000

### 3. Or run each stack directly

**Backend**
```bash
cd backend
uv venv && uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

---

## Testing, linting, type-checking

**Backend**
```bash
cd backend
uv run pytest             # tests
uv run ruff check .       # lint
uv run black --check .    # format
uv run mypy               # types
```

**Frontend**
```bash
cd frontend
npm test                  # vitest
npm run lint              # eslint
npm run format:check      # prettier
npm run typecheck         # tsc
```

CI runs all of the above on every push — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

Optional local hooks: `pre-commit install`.

---

## Repository layout

```
gridscore/
├── backend/    FastAPI service, ML platform, providers, tests
├── frontend/   React SPA (operator / lender / admin consoles)
├── infra/      docker-compose (dev & prod), render.yaml, CI
├── scripts/    seed & dev helpers
└── docs/       architecture, decisions, data model, stage reports
```

---

## License

Proprietary — built for a startup competition and as the seed of the product.
# Gridscore AI
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
