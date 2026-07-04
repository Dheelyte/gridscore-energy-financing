# Stage 6 Report — Ingestion & Enrichment Pipeline

## 1. Stage name & objective
**Stage 6 — Ingestion & enrichment.** How data safely enters the cooperative:
validated batch/stream ingestion of repayment events with **anonymisation at the
boundary** (no raw PII ever persisted), dedup/idempotency and per-row error
reporting, processing by an **arq** background worker, swappable **provider
adapters** (mobile-money / airtime / utility) behind ports with mock impls, and a
**consent-gated enrichment** job that pulls signals and recomputes features.
Acceptance: a batch flows validation → worker → persisted events → enrichment →
recomputed features → changed score, and the PII-leak test passes.

## 2. What was built
- **Anonymisation** (`app/services/ingestion/anonymise.py`) — `hash_identity`
  (normalise → salted SHA-256). The raw national ID / phone is hashed at the edge
  and **never stored**.
- **Provider ports + mocks** (`app/providers/`) — abstract `MobileMoneyProvider`,
  `AirtimeProvider`, `UtilityProvider` (hexagonal ports) with deterministic mock
  adapters (seeded from the identity hash) and a `registry.default_providers()`
  swap point (ADR-0024).
- **Ingestion service** (`app/services/ingestion/service.py`) — per-row Pydantic
  validation (`RawRepaymentRow`), anonymise, get-or-create customer with captured
  consent, **idempotent dedup** on `(customer, operator, due_date)` (ADR-0025),
  and an `IngestionReport` (received / inserted / duplicates / failed / per-row
  errors). CSV + JSON parsing (`parsing.py`).
- **Enrichment service** (`enrichment.py`) — **consent-gated** (skips without
  `ENRICHMENT` consent), persists `enrichment_signal` rows via the providers, then
  materialises a fresh pooled `feature_snapshot`.
- **Shared pipeline** (`pipeline.py`) — `process_ingestion(...)` runs ingestion
  then enrichment; used by both the API (inline) and the worker.
- **arq worker** (`app/workers/`) — `ingest_batch` task + `WorkerSettings`
  (engine/session on startup) + an enqueue helper; the compose/render `worker`
  service now runs `arq app.workers.main.WorkerSettings`.
- **API** (`app/api/v1/ingestion.py`) — `POST /v1/ingest/events` (inline, returns
  the report), `POST /v1/ingest/batch` (CSV/JSON file → enqueue to the worker, or
  inline fallback if no worker), `GET /v1/ingest/jobs/{id}` (job status). The API
  loads an arq pool at startup (best-effort).
- **Refactor** — a shared `app/services/feature_io.py` builds the feature-pipeline
  input for both scoring and enrichment (one code path).

## 3. Key decisions & trade-offs
- **ADR-0024** — provider ports + mock adapters; on-read feature recomputation.
- **ADR-0025** — idempotency key `(customer, operator, due_date)`.
- Ingestion captures `DATA_SHARING`, `ENRICHMENT`, `SCORING` consent for new
  customers (the operator attests at onboarding); enrichment still re-checks
  `ENRICHMENT` consent at run time.
- Batch endpoint **degrades to inline** when no worker/Redis is wired, so uploads
  work in dev without an arq worker, while production runs the async path.

## 4. File tree delta
```
backend/app/services/ingestion/{__init__,anonymise,schemas,parsing,service,
                                 enrichment,pipeline}.py   (new)
backend/app/services/feature_io.py                          (new, shared)
backend/app/providers/{base,mock,registry}.py              (new)
backend/app/workers/{ingest,main,queue}.py                 (new)
backend/app/api/v1/ingestion.py                            (new) + router/main wiring
backend/app/db/repositories/repositories.py                (existing_due_dates)
backend/app/services/scoring/service.py                    (use feature_io)
backend/tests/unit/{test_anonymise,test_providers,test_ingestion_parsing}.py (new)
backend/tests/integration/test_ingestion.py                (new) + test_api.py (ingest)
infra/docker-compose.yml, docker-compose.prod.yml, render.yaml (worker=arq)
frontend/openapi.json, src/lib/api/schema.ts               (regenerated, 18 paths)
docs/DECISIONS.md (ADR 0024-0025), README.md
```

## 5. How to run it (from a clean checkout)
```bash
docker compose -f infra/docker-compose.yml up --build   # api + arq worker + redis + pg

# Inline ingestion (no worker needed):
curl -s -X POST localhost:8000/v1/ingest/events -H "X-API-Key: <key>" \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"raw_identifier":"+254700111000","instalment_amount":"12.50",
       "currency":"USD","due_date":"2024-05-05","status":"on_time"}]}'

# Batch file → background worker:
curl -s -X POST localhost:8000/v1/ingest/batch -H "X-API-Key: <key>" -F file=@batch.csv
#   -> {"job_id":"...","status":"queued","received":N}
# Run the worker standalone: cd backend && uv run arq app.workers.main.WorkerSettings
```

## 6. How to test it (with actual results)
```bash
cd backend
uv run ruff check .   # All checks passed!
uv run black --check . # unchanged
uv run mypy           # Success (96 source files)
uv run pytest -q      # full suite
```
**Stage 6 tests: 20 passed** (anonymise + providers + parsing unit, ingestion
integration) plus an API ingestion test. They cover:
- **validation**: per-row errors don't abort the batch (2 inserted, 2 failed).
- **idempotency**: re-ingesting a batch inserts 0, reports all as duplicates.
- **anonymisation / PII-leak**: the raw phone never appears in the DB; the stored
  `identity_hash` equals the salted SHA-256; a `LIKE '%+254%'` scan returns 0.
- **provider contracts**: each mock returns the expected keys/ranges,
  deterministic per identity, varying across customers.
- **consent-gating**: a customer without `ENRICHMENT` consent yields no signals.
- **end-to-end**: ingest thin/late history → score; ingest fuller on-time history
  + enrichment → **score improves and PD drops** (the acceptance flow).

## 7. Screencap / demo notes
- `POST /v1/ingest/events` in `/docs` returns the live `IngestionReport`.
- After a batch, `enrichment_signal` rows (3 per consented customer) and a fresh
  pooled `feature_snapshot` appear; re-scoring shows the improved number.

## 8. Known issues & gaps
- **No raw-batch persistence / audit table** for uploads beyond the arq job
  result; a durable `ingestion_batch` ledger is a nice future addition.
- Dedup is monthly granularity (`due_date`); sub-monthly cadence would need a
  finer key (ADR-0025).
- The batch endpoint's worker path needs Redis + a running arq worker; tests
  exercise the inline path and the worker task function directly.
- Mock providers are synthetic; real telco/Open Banking adapters are deliberately
  deferred (the ports make them drop-in).

## 9. What Stage 7 will do
**Stage 7 — Operator console (frontend).** The screen-recorded dashboard: login +
role-aware shell, customer score lookup (gauge, PD, tier, SHAP top factors), the
**cooperative panel** (animated solo-vs-pooled with the reject→approve flip on the
borderline customer — the money shot), a portfolio overview, and a data-upload UI
wired to this stage's ingestion — with Vitest component tests and a Playwright
e2e against the live backend.

## 10. Approval gate
**Stage 6 complete — awaiting approval to proceed.**
