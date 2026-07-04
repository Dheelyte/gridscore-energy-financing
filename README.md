# GridScore AI

### The shared credit bureau for Africa's pay-as-you-go energy lenders.

> A good borrower who is *new to you* looks identical to a defaulter. So lenders
> reject people who would have repaid — and a continent stays under-financed.
> **GridScore fixes that with a repayment data cooperative that makes every
> lender's scoring sharper the moment another one joins.**

<p>
  <a href="https://gridscore-energy-financing.vercel.app/"><b>▶ Try the live app</b></a>
  &nbsp;·&nbsp;
  <a href="docs/DEMO_SCRIPT.md">3-min demo script</a>
  &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md">Architecture</a>
  &nbsp;·&nbsp;
  <a href="docs/ROADMAP.md">Roadmap</a>
</p>

---

## ✅ It's built, tested, and deployed — click in and log in

**Live app → https://gridscore-energy-financing.vercel.app/**

This is not a slide deck. It's a working, multi-tenant platform you can sign into
right now. The login screen has **one-click demo logins for every role** — no
setup:

| Click this role | Email | What you'll see |
|---|---|---|
| **Operator analyst** | `analyst@gridscore.ai` | Score a customer → **watch a rejection become an approval** under the pooled view |
| **Lender / DFI** | `lender@gridscore.ai` | The **network-effect chart**: accuracy climbing as operators join |
| **Platform admin** | `admin@gridscore.ai` | Operators, users, the active model, and the immutable audit log |

**Password for all demo accounts:** `GridScore!Demo1`

A **60-second guided tour** launches automatically on first login and shows you
exactly where to click. Everything runs on **synthetic data**, clearly labelled.

> First page load may take a few seconds while the free-tier API wakes up. If you
> ever see "API offline," give it ~30s and refresh.

---

## The problem (and why it's worth solving)

Across Sub-Saharan Africa, PAYG solar and appliance lenders finance millions of
households on tiny instalments. But each lender keeps its **own siloed** repayment
history. The consequences:

- A customer who **defaulted** with Operator A can walk to Operator B and get a
  fresh loan the same day.
- A customer who **reliably repaid** — but is new to Operator B — gets **rejected**
  for lack of a track record.

Both errors are expensive. The fix isn't a better model in one silo; it's a
**shared signal** across all of them.

## The solution — a repayment data cooperative

Operators contribute **anonymised** repayment histories through one standard API.
GridScore enriches them with mobile-money, airtime, and utility signals and
returns an **Energy Credit Score (300–850)** plus a calibrated **default
probability** and SHAP reason codes.

The defensible core — the thing that makes this **infrastructure, not a feature** —
is the **cooperative network effect**: *every operator who joins makes everyone
else's scoring measurably better.* That's a data moat that compounds.

---

## The proof (we *demonstrate* the moat, we don't assert it)

Judges: these are the two artifacts to look at. Both are live in the app.

### 1 · The decision flips — same customer, reject → approve
The borderline demo customer, scored two ways against the **same model at the same
instant**:

| View | On-time history | Default prob. | Score | Decision |
|---|---|---|---|---|
| **Solo** (home operator only) | ~33% over ~3 months | **0.164** | 612 (C) | ❌ **Reject** |
| **Pooled** (full cooperative) | ~93% over ~28 months | **0.066** | 686 (B) | ✅ **Approve** |

The customer is genuinely reliable — the solo lender just couldn't see it. **That
gap is the product.** (Operator-analyst console → "Borderline demo customer".)

### 2 · The network effect is real
Retrain on a growing number of operators and held-out **AUC rises ~0.69 → ~0.74**
as the pool grows. More contributors → better scoring for all. (Lender analytics.)

### Honest by construction
- Model AUC sits in a **realistic 0.70–0.82** band. Training **flags any AUC > 0.90**
  as a target-leakage smell — we'd rather show believable numbers than a suspicious
  0.99.
- **No raw PII is ever stored.** National IDs and phone numbers become salted
  SHA-256 hashes at ingestion; a test asserts the raw value never reaches the DB.
- **Every score and data access is written to an immutable audit log** (a database
  trigger rejects UPDATE/DELETE). Scoring is **consent-gated**.

---

## Why this wins

- **Real product, running today** — deployed, sign-in-able, with role-based
  consoles for the three actual customer types (operators, lenders/DFIs, platform).
- **A defensible moat** — the network effect compounds with every operator; it's
  the kind of thing that becomes a category-defining bureau.
- **Built to a production bar, not a demo bar** — async FastAPI, typed end-to-end,
  multi-tenant isolation, migrations, background workers, observability, a security
  pass, and CI. **Full test suite green (backend 114 passed, 91% on the
  domain/services surface; frontend green).**
- **Trustworthy** — a credit bureau lives or dies on trust; privacy, auditability,
  and honest metrics are in the **code**, not just the pitch.

---

## What's inside (11 stages, all complete)

| # | Stage | # | Stage |
|--:|---|--:|---|
| 0 | Foundation & scaffolding | 6 | Ingestion & enrichment pipeline |
| 1 | Domain & data model | 7 | Operator console (frontend) |
| 2 | Synthetic data engine | 8 | Lender/DFI analytics & platform admin |
| 3 | ML platform (train / registry) | 9 | Observability, hardening & security |
| 4 | Scoring & cooperative lift | 10 | Deployment, docs & demo packaging |
| 5 | Multi-tenant API & auth | | |

Each stage has a report in [`docs/stages/`](docs/stages/); every non-trivial
decision is logged in [`docs/DECISIONS.md`](docs/DECISIONS.md) (30 ADRs).

**Stack:** Python 3.12 · FastAPI (async) · Pydantic v2 · SQLAlchemy 2.0 + Alembic ·
PostgreSQL 16 · Redis + arq workers · XGBoost + SHAP + MLflow · React + TypeScript +
Vite + Tailwind/shadcn + TanStack Query + Recharts · Docker · GitHub Actions CI ·
structlog + Prometheus + OpenTelemetry.

---

## Run it yourself in one command

```bash
git clone <this-repo> && cd gridscore
docker compose -f infra/docker-compose.yml up --build -d      # API, web, Postgres, Redis, MLflow
cd backend && uv run alembic upgrade head
uv run python ../scripts/seed_demo.py                          # synthetic data + demo logins
```
Open the frontend, sign in with a demo account above, and look up the borderline
customer. Full walkthrough: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).
Deployment (Render + Vercel or single-host): [`docs/RUNBOOK.md`](docs/RUNBOOK.md#deployment).

<details>
<summary>Run each stack directly (no Docker)</summary>

```bash
# Backend
cd backend && uv venv && uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8000        # http://localhost:8000/docs

# Frontend
cd frontend && npm install && npm run dev               # http://localhost:5173
```
</details>

<details>
<summary>Test · lint · type-check (CI runs all of these)</summary>

```bash
# Backend
cd backend && uv run pytest && uv run ruff check . && uv run black --check . && uv run mypy
# Frontend
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```
See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
</details>

---

## Architecture at a glance

A layered, multi-tenant, ports-and-adapters system: a React SPA → an async FastAPI
`/v1` gateway (JWT + hashed API keys, RBAC, rate limiting, per-operator isolation)
→ scoring / ingestion / analytics / consent services → SQLAlchemy on PostgreSQL 16
+ Redis, with an XGBoost + SHAP + MLflow ML platform and swappable provider
adapters. Full diagram and rationale in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

```
gridscore/
├── backend/    FastAPI service, ML platform, providers, tests
├── frontend/   React SPA (operator / lender / admin consoles + guided tour)
├── infra/      docker-compose (dev & prod), render.yaml, CI
├── scripts/    seed & dev helpers
└── docs/       architecture, decisions, data model, security, demo script, roadmap, stage reports
```

---

> ⚠️ **All data outside production is synthetic and clearly labelled as such.**
> Metrics are deliberately realistic, not perfect — see the honesty posture in
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**License:** Proprietary — built for a startup competition and as the seed of the product.
