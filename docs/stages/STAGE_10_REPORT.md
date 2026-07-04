# Stage 10 Report — Deployment, Docs & Demo Packaging

## 1. Stage name & objective
**Stage 10 — ship it and make it presentable.** Make the platform deployable
(managed + single-host), document the exact deploy and demo procedures, and
package the pitch: a timed demo script anchored on the reject→approve flip, a
roadmap of honestly-deferred production work, and final docs polish. This is the
**final stage** of the 0–10 build.

## 2. What was built
- **Deploy migration fix (ADR-0029)** — the backend image was missing
  `alembic.ini`, and nothing applied migrations on deploy. Now: `alembic.ini` is
  copied into the runtime image; **Render** applies migrations via
  `preDeployCommand: alembic upgrade head` on the API service; the **prod compose**
  has a one-shot `migrate` service that `api`/`worker` wait on
  (`service_completed_successfully`). The prod compose also **publishes the API
  port** (the SPA calls the API directly via `VITE_API_BASE_URL`).
- **Vercel config** (`frontend/vercel.json`) — Vite framework preset, SPA rewrite
  to `index.html`, immutable caching for hashed assets.
- **RUNBOOK deployment section** — full env-var table (what/where/notes), the
  Render+Vercel path and the single-host compose path, how to seed the deployed
  DB, and a post-deploy smoke check (`/health`, `/ready`, `/metrics`).
- **`docs/DEMO_SCRIPT.md`** — a timed (~3:00) walkthrough with the **deterministic
  borderline customer** (stable identity hash), exact solo vs pooled figures, the
  two money-shot artifacts, honesty guardrails, and live-failure recovery steps.
- **`docs/ROADMAP.md`** — what's done vs. deferred (data onboarding, model
  lifecycle, fairness/regulation, security/compliance, HA/ops, dependency bumps),
  plus explicit out-of-scope items.
- **Docs polish** — README status table now all-complete with deploy/demo/roadmap
  pointers; ADR-0029 added.

## 3. Key decisions & trade-offs
- **ADR-0029** — migrations are a **release step**, never run by hand against
  prod; both deploy paths converge the schema before serving traffic.
- **SPA calls the API directly** (build-time `VITE_API_BASE_URL`) rather than
  proxying through nginx — simpler, but CORS must list the SPA origin and the API
  must be publicly reachable (documented).
- **Demo customer identity hash is deterministic** (`sha256("gridscore-demo-
  borderline-0001")`, salt-independent) so the flip is reproducible across
  deploys and can be hard-referenced in the script.

## 4. File tree delta
```
backend/Dockerfile                 (COPY alembic.ini into runtime image)
infra/render.yaml                  (preDeployCommand: alembic upgrade head)
infra/docker-compose.prod.yml      (migrate one-shot; api port published; deps)
frontend/vercel.json               (new — Vite SPA build + rewrites)
docs/DEMO_SCRIPT.md                (written — timed walkthrough)
docs/ROADMAP.md                    (new — deferred production work)
docs/RUNBOOK.md                    (deployment section filled in)
docs/DECISIONS.md                  (ADR-0029)
README.md                          (status all-complete + doc pointers)
docs/stages/STAGE_10_REPORT.md     (this report)
```

## 5. How to run it
Local (unchanged): `docker compose -f infra/docker-compose.yml up --build`.
Single-host production-style:
```bash
cp .env.example .env.prod   # fill real secrets (see RUNBOOK env table)
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build
# postgres/redis healthy → migrate (alembic upgrade head) → api(:8000) + worker; SPA :8080
```
Managed: Render Blueprint from `infra/render.yaml` (API+worker+PG+Redis) + Vercel
(root `frontend/`, set `VITE_API_BASE_URL`). Full steps: `docs/RUNBOOK.md`.

## 6. How to test it (with actual results)
- **Prod compose config validates**: `docker compose -f infra/docker-compose.prod.yml
  config` → **OK** (with required env set).
- **render.yaml** parses as valid YAML → **OK**.
- **Alembic config resolves** in the app venv: `alembic heads` →
  `0002_synthetic_profile (head)` (confirms `script_location`/`prepend_sys_path`).
- **`alembic.ini` (and `pyproject.toml`, `README.md`) are present in the Docker
  build context** with no `.dockerignore`, so the new `COPY` line succeeds; the
  **`alembic` console script is installed** (`.venv/bin/alembic`, v1.18.4), so the
  `alembic upgrade head` command in the migrate step / `preDeployCommand` resolves
  on the image PATH.
- **Backend image build** (`docker build ./backend`): **not completed here** — it
  timed out at 540s during dependency download (numpy/xgboost/scipy) under this
  environment's constrained network (exit 124), *before* any Dockerfile logic
  error could occur. The change is a file `COPY` of files verified present; CI's
  `docker` job builds the image on every run.
- No application code changed, so the Stage 9 suites (backend 114 passed / 91%
  coverage; frontend Vitest 8 passed; ruff/black/mypy clean) remain the
  behavioural baseline.

## 7. Screencap / demo notes
The pitch is scripted in `docs/DEMO_SCRIPT.md`: look up the borderline customer
(hash `e5d859ae…38d9`), show **solo → REJECT** (~33% on-time / ~3 mo), toggle to
**pooled → APPROVE** (~93% / ~28 mo), then the **AUC-vs-operators** chart
(≈0.69→0.74). Honesty guardrails are in the script.

## 8. Known issues & gaps
- **Not deployed to a live URL here** — this environment has no cloud credentials;
  Stage 10 delivers verified, reproducible deploy *artifacts + runbook*, not a
  running public instance. Deploying is a credentials-only step from the RUNBOOK.
- Residual Starlette advisories and other deferred items are tracked in
  `docs/ROADMAP.md` / `docs/SECURITY.md`.
- The single-host compose is "production-style" for demos/VPS, not a HA topology
  (no replicas/backups) — see the roadmap.

## 9. What comes next
The 0–10 build is complete. Beyond it, `docs/ROADMAP.md` sequences a production
build: real data onboarding, model lifecycle (retraining/champion-challenger/
drift alerts), fairness & adverse-action reporting, auth hardening
(refresh-token rotation, lockout), KMS-managed salt + encryption at rest, OTLP/
Grafana + SLOs, HA Postgres/Redis, and the Starlette ≥1.x bump.

## 10. Approval gate
**Stage 10 complete — the full 0–10 build is done, awaiting final approval.**
