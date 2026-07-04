# Stage 1 Report — Domain & Data Model

## 1. Stage name & objective
**Stage 1 — Domain & data model.** Build the persistent core of GridScore AI:
all twelve §5 entities as SQLAlchemy 2.0 (async) models with relationships and
constraints; an Alembic migration that creates the schema — including monthly
**partitioning** of the high-volume `repayment_event` table, the documented
**indexing plan**, and an **immutable** audit log; a clean **repository layer**
separated from services; real Postgres/Redis **readiness checks**; full data-
model documentation; and a test suite that runs against a **real PostgreSQL** via
testcontainers. Acceptance: migrations apply to an empty DB and roll back, and
repository tests pass.

## 2. What was built
- **Domain vocabulary** — `app/domain/enums.py`: 9 `StrEnum`s (operator/user
  status, roles, consent scope, repayment status, provider type, score view,
  risk tier, promotion stage) stored as native PostgreSQL ENUM types.
- **DB foundation** — `app/db/base.py` (declarative `Base` with a deterministic
  constraint-naming convention, `UUIDPrimaryKeyMixin`, `TimestampMixin`,
  `pg_enum` helper); `app/db/types.py` (RFC 9562 **UUIDv7** generator + timestamp
  extractor, no native dependency).
- **Models** (`app/db/models/`) for all 12 entities, grouped by aggregate:
  `tenancy` (operator, user_account, api_credential), `customer` (customer,
  consent_record), `events` (repayment_event, enrichment_signal), `scoring`
  (feature_snapshot, score_result, cooperative_lift), `platform` (audit_log,
  model_version) — with relationships, `passive_deletes`, CHECK constraints
  (score ∈ [300,850], PD ∈ [0,1]), and JSONB payloads.
- **Async persistence** — `app/db/session.py` (engine + session factory +
  transactional `get_session` dependency) and `app/db/redis.py` (async client).
  Wired into the app factory and disposed on shutdown.
- **Repository layer** — `app/db/repositories/`: a generic `BaseRepository`
  (typed CRUD) plus one repository per aggregate with intention-revealing
  queries, including the **solo vs pooled** repayment-history reads and
  active-consent resolution.
- **Readiness probe** — `/ready` now performs bounded Postgres `SELECT 1` and
  Redis `PING` checks (overridable dependencies), returning **503** when degraded.
- **Alembic** — config + async `env.py` (URL injected from settings, never
  committed) + hand-written `0001_initial`: standard tables created from
  `Base.metadata` (no drift), `repayment_event` partitioned by month (48 monthly
  partitions + DEFAULT), parent indexes, and the audit-log immutability trigger.
- **Docs** — `docs/DATA_MODEL.md` (ER overview, per-table reference, partitioning
  & indexing rationale, transaction model) and 5 new ADRs (0008–0012).

## 3. Key decisions & trade-offs
New entries in [`docs/DECISIONS.md`](../DECISIONS.md):
- **ADR-0008** — UUIDv7 primary keys (time-ordered; healthy indexes/partitions).
- **ADR-0009** — migration creates standard tables from metadata (single source
  of truth) and uses raw DDL only for the partitioned table + trigger.
- **ADR-0010** — `repayment_event` range-partitioned by month on `due_date`.
- **ADR-0011** — `passive_deletes` so DB-level FK actions are authoritative.
- **ADR-0012** — audit-log immutability enforced by a DB trigger.

Trade-off worth noting: the initial migration is intentionally **not** a pure
autogenerate diff. Driving the bulk of the schema from `Base.metadata` keeps it
in lock-step with the models, while the irreducible partitioning/trigger DDL is
explicit and reviewable (documented in the migration header).

## 4. File tree delta
```
backend/alembic.ini                                  (new)
backend/pyproject.toml                               (deps: sqlalchemy, asyncpg,
                                                      alembic, redis, greenlet,
                                                      testcontainers, psycopg2;
                                                      mypy override)
backend/uv.lock                                      (updated)
backend/app/main.py                                  (engine/redis wiring)
backend/app/api/health.py                            (real readiness checks)
backend/app/domain/enums.py                          (new)
backend/app/db/base.py                               (new)
backend/app/db/types.py                              (new)
backend/app/db/session.py                            (new)
backend/app/db/redis.py                              (new)
backend/app/db/models/__init__.py                    (new)
backend/app/db/models/{tenancy,customer,events,scoring,platform}.py (new)
backend/app/db/repositories/__init__.py              (new)
backend/app/db/repositories/{base,repositories}.py   (new)
backend/app/db/migrations/{env.py,script.py.mako}    (new)
backend/app/db/migrations/versions/0001_initial.py   (new)
backend/tests/conftest.py                            (app fixture)
backend/tests/unit/test_health.py                    (readiness tests updated)
backend/tests/unit/__init__.py                       (new)
backend/tests/integration/__init__.py                (new)
backend/tests/integration/conftest.py                (testcontainers harness)
backend/tests/integration/test_migrations.py         (new)
backend/tests/integration/test_repositories.py       (new)
backend/tests/integration/test_constraints.py        (new)
backend/tests/integration/test_partitioning.py       (new)
docs/DATA_MODEL.md                                   (filled in)
docs/DECISIONS.md                                    (ADR 0008–0012)
docs/ARCHITECTURE.md, README.md                      (status updates)
```

## 5. How to run it (from a clean checkout)
```bash
cp .env.example .env
cd backend && uv venv && uv pip install -e ".[dev]"

# Start a Postgres (compose brings up the whole stack):
docker compose -f ../infra/docker-compose.yml up -d postgres redis

# Apply migrations:
GRIDSCORE_DATABASE_URL=postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore \
  uv run alembic upgrade head

# Run the API; /ready now reports real Postgres + Redis health:
uv run uvicorn app.main:app --reload --port 8000
curl -s localhost:8000/ready        # {"status":"ok","dependencies":{"database":"ok","redis":"ok"}}
```
Roll back the schema: `uv run alembic downgrade base`.

## 6. How to test it (with actual results)
```bash
cd backend
uv run ruff check .     # → All checks passed!
uv run black --check .  # → 39 files unchanged
uv run mypy             # → Success: no issues found in 39 source files
uv run pytest -p no:cacheprovider --cov=app --cov-report=term-missing
```
**Result: 22 passed (7 unit + 15 integration), coverage 92%.** Integration tests
run against a **real PostgreSQL 16** started by testcontainers and migrated with
the actual Alembic migration. They cover:
- **Migration roundtrip** — fresh DB → `upgrade head` (asserts 62 tables, **49
  partitions**, 9 enum types, audit trigger present) → `downgrade base` (asserts
  zero tables/enums remain). *This is the Stage 1 acceptance criterion.*
- **Repository CRUD & queries** — operator/customer/user lookups, active-consent
  resolution (grant + expiry rules), and the **solo vs pooled** repayment views.
- **Constraints** — unique `identity_hash`, FK enforcement, score CHECK range,
  customer-delete **cascade**, operator-delete **RESTRICT**, and **audit-log
  immutability** (DB rejects UPDATE).
- **Partition routing** — an event lands in `repayment_event_2024_05`; an
  out-of-window event lands in `repayment_event_default`.

Manual verification also performed against a throwaway Postgres container:
`alembic upgrade head` then `downgrade base` both succeed cleanly.

## 7. Screencap / demo notes
Nothing user-facing changed visually. For a reviewer:
- `uv run alembic upgrade head` then inspect with `psql`: `\dt+` shows the tables
  and `repayment_event_*` partitions; `\d+ repayment_event` shows
  `Partition key: RANGE (due_date)`.
- Attempt `UPDATE audit_log SET action='x';` in `psql` → it is rejected with
  *"audit_log is append-only"* — the immutability trigger in action.
- `curl localhost:8000/ready` with/without Postgres up shows `ok` vs a `503`
  `degraded` body.

## 8. Known issues & gaps
- **No service/business logic yet** — repositories exist but services that use
  them (scoring, ingestion) arrive in Stages 3–6. Several repository methods are
  not yet exercised by callers (hence the few uncovered lines).
- **Partition window is fixed (2023–2026)** in the migration; the automated
  roll-forward/`DETACH` maintenance job is deferred to the Stage 6 worker. The
  `DEFAULT` partition makes this safe in the meantime.
- **Integration tests require Docker** (testcontainers) and pull
  `postgres:16-alpine` on first run; CI provisions Docker for this.
- `model_version` is a convenience mirror of the MLflow registry; the
  authoritative registry is MLflow itself (Stage 3).

## 9. What Stage 2 will do
**Stage 2 — Synthetic data engine.** Build a configurable generator that creates
N customers with the Appendix A feature schema, where default is a real logistic
function of the features plus irreducible noise (~10–20% base rate). It models
the cooperative split (home operator + degraded **solo** history vs full
**pooled** history), persists everything through these Stage 1 models, and ships
a repeatable `scripts/seed_demo.py` containing at least one borderline customer
who flips reject→approve under the pooled view — with tests asserting the
distributions, default rate, and solo/pooled relationship hold.

## 10. Approval gate
**Stage 1 complete — awaiting approval to proceed.**
