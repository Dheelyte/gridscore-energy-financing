# GridScore AI — Architecture

> Living document. Seeded in Stage 0; expanded each stage as components land.

## 1. Goals & non-goals

**Goals**
- A genuinely impressive, production-credible multi-tenant credit platform.
- Demonstrate — not assert — the **cooperative network effect** (solo vs pooled).
- Privacy-by-design: no raw PII, consent-gated enrichment, immutable audit.
- Honest ML: realistic metrics, clearly-labelled synthetic data, explainability.

**Non-goals (deliberately deferred — see future `docs/ROADMAP.md`)**
- Real telco / Open Banking integrations (mock adapters now, ports defined).
- Formal model validation against real-world defaults.
- SOC2-style organisational controls.

## 2. System overview

```
        ┌──────────────────────── FRONTEND (SPA) ────────────────────────┐
        │   React + TS + Vite + Tailwind/shadcn                           │
        │   Operator console · Lender/DFI analytics · Platform admin      │
        └───────────────────────────────┬────────────────────────────────┘
                                         │ HTTPS / JSON (generated OpenAPI client)
        ┌───────────────────────────────▼────────────────────────────────┐
        │                        API GATEWAY (FastAPI)                    │
        │   AuthN/Z (JWT users + hashed API keys), RBAC, rate limiting,   │
        │   request audit, versioned /v1, OpenAPI                         │
        └───────┬─────────────────────┬──────────────────────┬───────────┘
                │                     │                      │
        ┌───────▼──────┐     ┌────────▼────────┐    ┌────────▼─────────┐
        │ SCORING svc  │     │ INGESTION svc   │    │ ANALYTICS svc    │
        │ features,    │     │ batch+API,      │    │ portfolio risk,  │
        │ inference,   │     │ consent,        │    │ cooperative      │
        │ solo/pooled, │     │ anonymisation   │    │ health metrics   │
        │ SHAP explain │     │ async jobs      │    │                  │
        └──────┬───────┘     └───────┬─────────┘    └────────┬─────────┘
               │                     │                       │
        ┌──────▼─────────────────────▼───────────────────────▼──────────┐
        │                    DOMAIN / DATA LAYER                         │
        │  SQLAlchemy 2.0 models · repositories · Alembic migrations     │
        │  PostgreSQL 16 (system of record) · Redis 7 (cache/queues)     │
        └──────┬───────────────────────────────────────────┬────────────┘
               │                                            │
        ┌──────▼───────────┐                    ┌───────────▼────────────┐
        │  ML PLATFORM      │                    │  PROVIDER ADAPTERS      │
        │  training, MLflow │                    │  MobileMoney/Airtime/   │
        │  registry, SHAP,  │                    │  Utility ports (mock →  │
        │  model cards,     │                    │  real later)            │
        │  drift monitor    │                    │                         │
        └───────────────────┘                    └─────────────────────────┘

Cross-cutting: structured logging, Prometheus metrics, health/readiness probes,
OpenTelemetry traces, Docker, GitHub Actions CI.
```

## 3. Key architectural decisions (summary)

The authoritative, dated log is [`DECISIONS.md`](DECISIONS.md). Highlights:

- **Hexagonal (ports & adapters)** so external integrations (telco, banking) are
  swappable behind interfaces — mocks today, real tomorrow, no core changes.
- **Async end-to-end** (FastAPI + SQLAlchemy async + asyncpg) for I/O-bound
  scoring/ingestion workloads.
- **uv** for Python dependency management (fast, reproducible, lockable).
- **Multi-tenant via a tenant (`operator`) discriminator** with enforced row
  scoping in the repository/service layer — never trust the client for tenancy.
- **OpenAPI-generated TypeScript client** so frontend and backend contracts
  cannot silently drift.

## 4. Backend layering (dependency direction points inward)

```
api  →  services  →  domain (entities, repositories)  →  db
                 ↘   providers (ports)
                 ↘   ml (features, inference, explain)
core (config, logging, security) is shared by all layers.
```

- `api/` — HTTP concerns only (routing, request/response schemas, auth deps).
- `services/` — use-cases / orchestration (scoring, ingestion, analytics, consent).
- `domain/` — entities, value objects, repository interfaces.
- `db/` — SQLAlchemy models, session, Alembic migrations.
- `ml/` — data generation, feature engineering, training, registry, explainability.
- `providers/` — enrichment ports + mock adapters.
- `workers/` — background jobs (arq).

## 5. Configuration & observability

- **Twelve-factor**: all config from the environment via `pydantic-settings`
  (`GRIDSCORE_` prefix). Secrets typed as `SecretStr`. See `.env.example`.
- **Structured logging** via `structlog` — console in dev, JSON in prod, with a
  correlation `request_id` (middleware from Stage 5/9).
- **Health/readiness** probes from Stage 0 (`/health`, `/ready`); Prometheus
  metrics and OpenTelemetry traces land in Stage 9.

## 6. Privacy & compliance posture (in code, not just docs)

- **No raw PII** — customer identity is a salted SHA-256 hash computed at the
  ingestion boundary; the raw identifier is never persisted.
- **Consent records** gate enrichment and scoring; scoring degrades/refuses
  without valid consent.
- **Immutable audit log** for every score request and data access.
- **Configurable data retention** with a purge job (Stage 9).

## 7. Honesty posture (a feature for technical judges)

- Synthetic data is labelled synthetic everywhere it surfaces (UI banner, API
  metadata, docs).
- Model performance targets a realistic **AUC ~0.70–0.82**; suspiciously high
  scores are treated as a leakage bug to investigate, not a win.
- Deferred production work is tracked openly so reviewers see scope was a choice.

## 8. Current state (through Stage 1)

- **Stage 0** — async FastAPI app, typed settings, structured logging, React/
  Tailwind landing page, Docker Compose stack (api, worker, postgres, redis,
  mlflow, frontend), CI.
- **Stage 1** — the full persistent core: SQLAlchemy 2.0 models for all 12
  entities, the repository layer, async engine/session + Redis client, real
  Postgres/Redis readiness checks on `/ready`, and an Alembic migration with
  monthly partitioning of `repayment_event` and an immutable `audit_log`.
  See [`DATA_MODEL.md`](DATA_MODEL.md). Tested against a real Postgres via
  testcontainers.

- **Stage 2** — the synthetic data engine: a seeded generator producing
  cooperative data with genuine (logistic + irreducible-noise) predictive
  structure, a ~15% default rate, the solo/pooled split, and a curated
  borderline customer. Persisted via a bulk writer; `scripts/seed_demo.py`.
- **Stage 3** — the ML platform: a deterministic feature pipeline (solo/pooled),
  an XGBoost + isotonic-calibration training pipeline logged to **MLflow** with a
  versioned registered model, SHAP per-prediction explanations, an auto-generated
  **model card**, and a PSI **drift monitor**. `scripts/train_model.py`.

Next: Stage 4 (scoring service) turns the model into score + tier + explanation +
the cooperative lift.
