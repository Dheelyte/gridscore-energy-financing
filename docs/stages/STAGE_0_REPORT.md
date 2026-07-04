# Stage 0 Report — Foundation & Scaffolding

## 1. Stage name & objective
**Stage 0 — Foundation & scaffolding.** Establish a clean, runnable, production-
shaped skeleton for GridScore AI with all tooling wired and **no business logic
yet**. The deliverable is a full-stack that boots: an async FastAPI backend with
health/readiness probes, a React/Tailwind landing page that pings the API, a
Docker Compose stack (api, worker, postgres, redis, mlflow, frontend), linting/
formatting/type-checking on both stacks, pre-commit hooks, GitHub Actions CI, and
seed documentation. This stage proves the engineering substrate is sound before
any domain code is written.

## 2. What was built
- **Repository skeleton** exactly matching the project's §4 layout (`backend/`,
  `frontend/`, `infra/`, `scripts/`, `docs/` with `model_cards/` and `stages/`).
- **Backend (FastAPI, async, Python 3.12, uv):**
  - `app/main.py` — application factory + ASGI entrypoint, CORS, lifespan hook,
    service banner at `/`.
  - `app/api/health.py` — `GET /health` (liveness) and `GET /ready` (readiness;
    dependency map empty until Stage 1) with typed Pydantic responses.
  - `app/core/config.py` — twelve-factor settings via `pydantic-settings`
    (`GRIDSCORE_` prefix), secrets as `SecretStr`, CORS CSV parsing, env enum.
  - `app/core/logging.py` — `structlog` pipeline (console in dev, JSON in prod).
  - Package markers for `db/ domain/ services/ ml/ providers/ workers/` (the
    layered structure is visible from day one; implemented in later stages).
  - `Dockerfile` — multi-stage, uv-based, non-root user, container HEALTHCHECK.
- **Frontend (React 18 + TS + Vite + Tailwind + shadcn-style):**
  - Vite + TS project, path alias `@/*`, strict `tsconfig`.
  - Tailwind config + design tokens (`globals.css`) — a deep "grid green" energy-
    fintech palette, not a stock template.
  - A hand-rolled shadcn-style `Button` primitive (`cva` + `cn`), no CLI needed.
  - `App.tsx` landing page: product headline, **synthetic-data honesty banner**,
    a live **API status badge** that pings `/health`, and three feature cards
    (cooperative network effect, privacy by design, explainable ML).
  - `Dockerfile` — multi-stage build → nginx static serve with SPA fallback.
- **Infra:**
  - `infra/docker-compose.yml` — dev stack: postgres, redis, mlflow, api,
    worker (placeholder), frontend, with healthchecks and dependency ordering.
  - `infra/docker-compose.prod.yml` — single-host production-style stack with
    required-secret env interpolation.
  - `infra/render.yaml` — Render blueprint (Postgres, Redis, api, worker).
- **Quality gates:**
  - Backend: ruff + black + mypy (strict) + pytest configured in `pyproject.toml`.
  - Frontend: eslint (flat config) + prettier + `tsc` + vitest.
  - `.pre-commit-config.yaml` covering both stacks + hygiene hooks.
  - `.github/workflows/ci.yml` — backend job, frontend job, docker-build job.
- **Docs:** root `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`
  (8 ADRs), plus seeded stubs for `DATA_MODEL.md`, `API.md`, `RUNBOOK.md`,
  `DEMO_SCRIPT.md` (each clearly marked with the stage that fills it in).
- **Config hygiene:** `.env.example`, `.gitignore`, `.dockerignore`.

## 3. Key decisions & trade-offs
Recorded in [`docs/DECISIONS.md`](../DECISIONS.md):
- **ADR-0000** — staged delivery with approval gates.
- **ADR-0001** — stack selection (FastAPI/React/Postgres/Redis/XGBoost).
- **ADR-0002** — OpenAPI-generated TS client (prevents contract drift; built S5).
- **ADR-0003** — hexagonal ports & adapters for swappable integrations.
- **ADR-0004** — multi-tenancy via `operator` discriminator with enforced scoping.
- **ADR-0005** — async end-to-end (FastAPI + SQLAlchemy async + asyncpg).
- **ADR-0006** — background jobs via **arq** over Celery (async-native).
- **ADR-0007** — **uv** for Python dependency management (fast, reproducible).

Notable trade-off: the `worker` service exists in compose from Stage 0 as an
idle placeholder so the topology is honest about its shape, with the real arq
entrypoint deferred to Stage 6 (where ingestion needs it).

## 4. File tree delta
All files are new this stage:
```
.gitignore  .env.example  .pre-commit-config.yaml  README.md
.github/workflows/ci.yml
backend/pyproject.toml  backend/uv.lock  backend/README.md  backend/Dockerfile
backend/app/__init__.py  backend/app/main.py
backend/app/core/{__init__,config,logging}.py
backend/app/api/{__init__,health}.py
backend/app/{db,domain,services,ml,providers,workers}/__init__.py
backend/tests/__init__.py  backend/tests/conftest.py
backend/tests/unit/test_health.py
frontend/package.json  frontend/package-lock.json
frontend/{tsconfig.json,tsconfig.app.json,tsconfig.node.json}
frontend/{vite.config.ts,tailwind.config.ts,postcss.config.js}
frontend/{eslint.config.js,.prettierrc.json,.prettierignore,.dockerignore}
frontend/{index.html,nginx.conf,Dockerfile}
frontend/public/grid.svg
frontend/src/main.tsx  frontend/src/vite-env.d.ts
frontend/src/app/{App.tsx,App.test.tsx}
frontend/src/components/ui/button.tsx
frontend/src/lib/utils.ts  frontend/src/styles/globals.css
frontend/src/test/setup.ts
infra/{docker-compose.yml,docker-compose.prod.yml,render.yaml}
infra/github-actions/README.md
scripts/README.md
docs/{ARCHITECTURE,DECISIONS,DATA_MODEL,API,RUNBOOK,DEMO_SCRIPT}.md
docs/stages/STAGE_0_REPORT.md
```

## 5. How to run it (from a clean checkout)
```bash
cp .env.example .env

# --- Whole stack via Docker ---
docker compose -f infra/docker-compose.yml up --build
#   API      http://localhost:8000/health   ·   docs /docs
#   Frontend http://localhost:8080
#   MLflow   http://localhost:5000

# --- Or each stack directly ---
cd backend && uv venv && uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8000     # http://localhost:8000

cd frontend && npm install && npm run dev            # http://localhost:5173
```

## 6. How to test it (with actual results)
**Backend** (`cd backend`):
```bash
uv run ruff check .      # → All checks passed!
uv run black --check .   # → 16 files unchanged
uv run mypy              # → Success: no issues found in 16 source files
uv run pytest -q         # → 6 passed
```
Coverage of the (intentionally tiny) Stage 0 surface: tests assert `/health` and
`/ready` return 200 with the documented bodies, the root banner, CORS CSV
parsing, secret redaction in `repr`, and the production env flag.

**Frontend** (`cd frontend`):
```bash
npm run typecheck      # → tsc clean (0 errors)
npx prettier --check   # → All matched files use Prettier code style!
npm run lint           # → 0 errors (1 react-refresh warning, non-blocking)
npm test               # → Test Files 1 passed · Tests 3 passed
npm run build          # → vite build OK (172 kB JS / 56 kB gzip)
```
Frontend tests assert the headline renders, the **synthetic-data label** is
present (honesty is a feature), and the cooperative-network-effect card shows.

**Infra:** `docker compose -f infra/docker-compose.yml config -q` and the prod
variant both validate successfully.

**Live probe verified:** running uvicorn locally, `curl /health` → `200`
`{"status":"ok","service":"gridscore-api",...}` and `/ready` → `200`
`{"status":"ok","dependencies":{}}`.

## 7. Screencap / demo notes
For a human verifier:
- Run the stack, open **http://localhost:8080** — the landing page should render
  the dark "grid green" UI with an **"API online"** badge (green dot) once it
  reaches the backend, and a visible *"Synthetic data only"* chip.
- Open **http://localhost:8000/docs** — Swagger UI lists `/`, `/health`, `/ready`.
- Nothing here is the pitch money-shot yet; the screen-recorded artifacts (the
  solo→pooled decision flip and the AUC-vs-operators chart) arrive in Stages 7–8.

## 8. Known issues & gaps
- **No business logic** — by design for Stage 0. `/ready` reports an empty
  dependency map; real Postgres/Redis readiness checks land in Stage 1.
- **npm dev-dependency advisories** — `npm install` reported 5 advisories
  (3 moderate / 1 high / 1 critical) in **build/test tooling** (transitive). The
  npm audit registry endpoint is unreachable from this build sandbox, so the
  specific CVEs are not enumerated here; they will be triaged in the **Stage 9
  security pass**. No impact on the shipped runtime bundle.
- **Docker images not built in this environment** — base-image pulls require
  network not available during this run. Compose files are config-validated and
  the app is verified running natively; full `docker compose up` should be run
  once on a networked machine to confirm image builds (CI's `docker` job does
  this on every push).
- **One eslint warning** — `react-refresh/only-export-components` on the Button
  primitive (exports `buttonVariants` alongside the component); standard shadcn
  pattern, non-blocking, lint exits 0.
- `worker` service is an idle placeholder until Stage 6.

## 9. What Stage 1 will do
**Stage 1 — Domain & data model.** Implement all §5 entities as SQLAlchemy 2.0
models with relationships and constraints; create Alembic migrations including
the monthly **partitioning** of `repayment_event` and the **indexing plan** for
hot lookups; add a clean repository layer separated from services; wire real
Postgres/Redis readiness checks into `/ready`; document the full ER model in
`docs/DATA_MODEL.md`; and cover models/repositories with unit tests against a
**testcontainers** Postgres (CRUD, constraints, cascade rules).

## 10. Approval gate
**Stage 0 complete — awaiting approval to proceed.**
