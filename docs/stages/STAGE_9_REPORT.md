# Stage 9 Report — Observability, Testing Hardening & Security Pass

## 1. Stage name & objective
**Stage 9 — make it production-credible.** Add observability (Prometheus metrics,
OpenTelemetry traces, structured logs with correlation IDs), harden the tests
(property-based tests, a latency benchmark + load-test harness), and run a
security pass (dependency audit, authz fuzzing, an OWASP checklist, a data-
retention purge job) plus a frontend accessibility pass. Acceptance: metrics +
traces visible locally; security checklist completed with findings addressed or
logged.

## 2. What was built
- **Observability** (`app/core/observability.py`, ADR-0027) — one ASGI middleware
  that binds a **`request_id`** to the structlog context (returned as
  `X-Request-ID`), opens an **OpenTelemetry** span (console exporter in dev),
  records **Prometheus** request count + latency histograms (route-template
  labels) and a `gridscore_scores_computed_total{view}` counter, and emits one
  structured access log per request. **`GET /metrics`** exposes the registry.
- **Data-retention purge** (`app/services/retention.py` + `app/workers/retention.py`,
  ADR-0028) — deletes derived artefacts (feature snapshots, score results,
  cooperative lifts) older than `GRIDSCORE_RETENTION_DAYS`; runs **nightly** via
  an arq cron. The immutable audit log and raw repayment events are retained.
- **Property-based tests** (Hypothesis) for the score transform: bounds,
  monotonicity, and tier consistency over the whole PD range.
- **Authz fuzzing** — parametrised tests that an operator principal can never
  reach admin/lender routes (403) and that cross-tenant customer sub-resources
  are 404; plus `/metrics` + correlation-ID assertions.
- **Load/perf** — an in-process scoring benchmark (`scripts/bench_scoring.py`) and
  a Locust file (`scripts/locustfile.py`) for the HTTP endpoint.
- **Security** — `docs/SECURITY.md` (controls + **OWASP Top-10 checklist**);
  `pip-audit` run; **bumped FastAPI 0.115→0.120 / Starlette 0.46→0.49.3** to clear
  several runtime advisories (residual logged).
- **Accessibility** — `aria-label`s on inputs and icon-only buttons,
  `aria-hidden` on decorative icons, `aria-current` via NavLink; a LoginPage
  accessible-names test.

## 3. Key decisions & trade-offs
- **ADR-0027** — metrics + traces + correlated logs in a single, legible
  middleware (route-template labels keep cardinality low).
- **ADR-0028** — purge derived/regenerable data; never the audit log or the raw
  cooperative signal.
- **Dependency posture (honest):** the Starlette bump cleared several CVEs; the
  remaining advisories list fixes only in Starlette ≥1.x, which FastAPI does not
  yet support — **logged** in `SECURITY.md`, to bump when FastAPI moves to 1.x.

## 4. File tree delta
```
backend/app/core/observability.py            (new)
backend/app/services/retention.py            (new)
backend/app/workers/retention.py             (new) + main.py cron
backend/app/main.py                          (register_observability)
backend/app/services/scoring/service.py      (scores metric)
backend/app/core/config.py                   (retention_days)
backend/scripts/{bench_scoring,locustfile}.py (new)
backend/tests/unit/test_transform_properties.py (new)
backend/tests/integration/test_retention.py  (new) + test_api.py (authz-fuzz,/metrics)
backend/pyproject.toml, uv.lock              (prometheus, otel, hypothesis,
                                              pip-audit; fastapi/starlette bump)
frontend/src/features/auth/LoginPage.{tsx,test.tsx}, admin/AdminPage.tsx (a11y)
docs/SECURITY.md (new), RUNBOOK.md (observability), DECISIONS.md (ADR 0027-0028)
```

## 5. How to run it
```bash
# Metrics + traces locally:
cd backend && uv run uvicorn app.main:app --port 8000
curl -s localhost:8000/metrics | grep gridscore_     # Prometheus
#   request spans print to the console (OTel ConsoleSpanExporter)

uv run python scripts/bench_scoring.py               # latency benchmark
uv run pip-audit                                     # dependency audit
locust -f scripts/locustfile.py --host http://localhost:8000   # load test
```

## 6. How to test it (with actual results)
```bash
cd backend && uv run ruff check . && uv run black --check . && uv run mypy && uv run pytest -q
cd frontend && npm run typecheck && npm run lint && npm test
```
- ruff / black / **mypy clean (108 files)**; **full backend suite: 114 passed**
  (incl. 4 Hypothesis property tests + the new integration tests) on the bumped
  FastAPI 0.120 / Starlette 0.49.3 — no regressions.
- New integration tests: **retention purge** (only old derived rows deleted),
  **authz-fuzz** (operator → privileged routes all 403; cross-tenant
  sub-resources all 404), **`/metrics`** served with the score counter + a
  correlation-ID header.
- **Frontend: Vitest 8 passed** (added a LoginPage accessibility test);
  typecheck / lint / build green.
- **Coverage = 91%** of the `app/services` + `app/domain` surface (branch
  coverage; 564 stmts, 34 missed). A **`fail_under = 85`** gate
  (`[tool.coverage.report]`) now enforces it; CI scopes `--cov` to that surface
  (the brief's ≥80% domain/services target).

### Performance (measured, in-process, 1 core)
Feature build + calibrated inference + SHAP: **p50 ≈ 5.3 ms, p95 ≈ 12 ms,
~159 scores/s/core.**

### Security summary
OWASP Top-10 checklist in `docs/SECURITY.md`: A01/A03/A07/A09/A10 ✅; A05/A06
⚠️ with documented prod actions. Findings addressed (Starlette bump) or logged
(residual Starlette ≥1.x advisories; mlflow/pyarrow training-time; pytest dev).

## 7. Screencap / demo notes
- `curl /metrics` shows the live Prometheus counters/histograms; the server
  console prints OpenTelemetry spans; every response carries `X-Request-ID`.
- Not a pitch-screen stage, but it's what makes judges trust the rest.

## 8. Known issues & gaps
- **Residual Starlette advisories** await FastAPI's move to Starlette 1.x (logged).
- OTel uses the **console exporter** in dev; wire an OTLP endpoint for prod.
- Coverage gate is scoped to `app/services` + `app/domain` (the brief's
  domain/services target), not the whole tree (API wiring/workers/mlflow logging
  branches are lower-value to cover).
- The load test (Locust) needs a running server + seeded data; the in-process
  benchmark gives the compute-path numbers without infra.

## 9. What Stage 10 will do
**Stage 10 — Deployment, docs & demo packaging.** Deploy backend + worker +
Postgres + Redis (Render) and the frontend (Vercel) with `render.yaml` /
`docker-compose.prod.yml` and a documented env + deploy runbook; seed the demo
scenario; write `docs/DEMO_SCRIPT.md` (the timed 3-minute walkthrough with the
exact borderline customer); final README/architecture/model-card polish; and
`docs/ROADMAP.md` of deliberately-deferred production items.

## 10. Approval gate
**Stage 9 complete — awaiting approval to proceed.**
