# Runbook

> Seeded in Stage 0; expanded with deploy/operate procedures through Stage 10.

## Local development

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

| Service   | URL                          | Notes                         |
|-----------|------------------------------|-------------------------------|
| API       | http://localhost:8000        | `/health`, `/ready`, `/docs`  |
| Frontend  | http://localhost:8080        | static SPA (nginx)            |
| MLflow    | http://localhost:5000        | experiment tracking/registry  |
| Postgres  | localhost:5432               | user/pass/db: `gridscore`     |
| Redis     | localhost:6379               | cache + job broker            |

Per-stack dev (hot reload) and test/lint commands: see the root `README.md`.

## Seed synthetic demo data

After migrations are applied, populate the cooperative with a repeatable
**synthetic** scenario (clearly labelled as synthetic in the database):

```bash
cd backend
GRIDSCORE_DATABASE_URL=postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore \
  uv run python ../scripts/seed_demo.py            # 2000 customers, resets first
# options: --customers N   --seed S   --no-reset
```

The summary prints the base default rate (~10–20%), the achievable feature-AUC
ceiling, and the **borderline demo customer** (identity hash + solo vs pooled
on-time rates) used for the reject→approve flip in the pitch.

The seed also creates three **demo login accounts** (synthetic; local demos only —
never seed these into production). All share the password **`GridScore!Demo1`**:

| Email | Role | Use |
|-------|------|-----|
| `admin@gridscore.ai` | platform_admin | platform admin, operator onboarding, analytics |
| `analyst@gridscore.ai` | operator_analyst | operator console + the decision flip (scoped to the demo customer's home operator) |
| `lender@gridscore.ai` | lender_viewer | lender/DFI analytics + the network-effect chart |

There is otherwise no bootstrap admin, so run the seed before first login.

## Tear down

```bash
docker compose -f infra/docker-compose.yml down          # keep volumes
docker compose -f infra/docker-compose.yml down -v       # wipe data
```

## Observability (Stage 9)

- **Metrics** — Prometheus at `GET /metrics`:
  - `gridscore_http_requests_total{method,path,status}` — request counts.
  - `gridscore_http_request_duration_seconds{method,path}` — latency histogram.
  - `gridscore_scores_computed_total{view}` — scores computed (solo/pooled).
  Point a Prometheus scrape at `/metrics`; a Grafana panel set: request rate by
  status, p50/p95 latency from the histogram, and scores/minute.
- **Tracing** — OpenTelemetry spans per request; the dev exporter is the console
  (`ConsoleSpanExporter`). Swap in an OTLP exporter via env for Tempo/Jaeger.
- **Logs** — structured (structlog); each request logs `method/path/status/
  duration_ms` bound to a **`request_id`** (also returned as `X-Request-ID`),
  so logs, traces, and the client correlate.

### Performance (indicative, in-process scoring compute, 1 core)
`python backend/scripts/bench_scoring.py` → **p50 ≈ 5.3 ms, p95 ≈ 12 ms,
~159 scores/s/core** (feature build + calibrated inference + SHAP). Load-test the
HTTP endpoint with `locust -f backend/scripts/locustfile.py`.

### Data retention
The arq worker runs a **nightly purge** (`purge_retention`, 03:00) deleting
derived artefacts (feature snapshots, score results, cooperative-lift rows) older
than `GRIDSCORE_RETENTION_DAYS` (default 365). Run on demand:
`uv run python -c "import asyncio; ..."` or trigger the arq job. The immutable
audit log is never purged.

## Deployment

Two supported targets, both migrated automatically on deploy:
**(A)** managed on **Render** (`infra/render.yaml`) + **Vercel** for the SPA, or
**(B)** a single host via **`infra/docker-compose.prod.yml`**. Migrations run as a
step in both paths (Render `preDeployCommand: alembic upgrade head`; a one-shot
`migrate` service in the prod compose) — never manually against prod.

### Environment variables

| Variable | Where | Notes |
|----------|-------|-------|
| `GRIDSCORE_SECRET_KEY` | api, worker | **≥32 bytes**, random; signs JWTs. `sync: false` on Render. |
| `GRIDSCORE_IDENTITY_HASH_SALT` | api, worker, migrate | Salt for identity hashing; **rotating it re-buckets identities** — set once, keep secret. |
| `GRIDSCORE_DATABASE_URL` | api, worker, migrate | `postgresql+asyncpg://…`. On Render, wired from the managed DB. |
| `GRIDSCORE_REDIS_URL` | api, worker | `redis://…`. On Render, wired from the Key-Value service. |
| `GRIDSCORE_CORS_ORIGINS` | api | Comma-separated allowed origins (the Vercel URL). |
| `GRIDSCORE_ENV` / `GRIDSCORE_LOG_JSON` | api, worker | `production` / `true` for JSON logs. |
| `VITE_API_BASE_URL` | frontend (**build-time**) | The public API URL the browser calls; baked into the SPA at build. |

Generate secrets: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Never commit them; `.env.example` holds placeholders only.

### A) Render + Vercel

1. **Backend/worker/DB/Redis** — in Render, *New → Blueprint*, point at this repo;
   Render reads `infra/render.yaml` and provisions Postgres 16, Key-Value (Redis),
   the `gridscore-api` web service, and the `gridscore-worker`. Enter the
   `sync: false` secrets (`GRIDSCORE_SECRET_KEY`, `GRIDSCORE_IDENTITY_HASH_SALT`,
   `GRIDSCORE_CORS_ORIGINS`) in the dashboard. The API `preDeployCommand` applies
   migrations before each release serves traffic; health-checks hit `/health`.
2. **Frontend** — in Vercel, import the repo with **root directory `frontend/`**
   (`frontend/vercel.json` handles the Vite build + SPA rewrites). Set the
   **Project env var `VITE_API_BASE_URL`** to the Render API URL, then deploy.
3. **CORS** — set `GRIDSCORE_CORS_ORIGINS` to the Vercel URL and redeploy the API.

### B) Single host (docker-compose.prod)

```bash
cp .env.example .env.prod        # then fill in real secrets (see table above)
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build
#   order: postgres/redis healthy → migrate runs `alembic upgrade head` → api + worker start
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod ps
```
API on `:8000` (`API_PORT` to override), SPA on `:8080`. Build the frontend with
`VITE_API_BASE_URL` pointing at the host's public API URL.

### Seed the deployed environment (optional, synthetic demo)

Run the seed **against the deployed database** once, for a live demo (see the
`seed_demo.py` section above; it resets by default — pass `--no-reset` to append).
The borderline demo customer's identity hash is deterministic and documented in
`docs/DEMO_SCRIPT.md`.

### Post-deploy smoke check

```bash
curl -fsS "$API_URL/health"           # {"status":"ok"}
curl -fsS "$API_URL/ready"            # dependencies healthy
curl -fsS "$API_URL/metrics" | head  # Prometheus exposition
```
Then open the SPA, log in, and confirm the operator console renders a score.

## Troubleshooting

- **`/ready` shows `degraded`** — a dependency (Postgres/Redis) check failed;
  inspect `docker compose ps` and service logs. (Dependency checks land in S1.)
- **Frontend shows "API offline"** — the API container is not reachable at
  `VITE_API_BASE_URL`; confirm the `api` service is healthy.
