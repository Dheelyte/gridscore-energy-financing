# Stage 5 Report — Multi-tenant API & Auth

## 1. Stage name & objective
**Stage 5 — Multi-tenant API & auth.** Expose the scoring engine as a secure,
versioned `/v1` B2B REST surface: dual authentication (JWT users + hashed API
keys), RBAC per route, strict **tenant isolation**, Redis-backed rate limiting,
a consistent error envelope, full OpenAPI docs, and a generated TypeScript client
so the SPA and backend cannot drift. Acceptance: an authenticated, rate-limited,
tenant-isolated API with OpenAPI served and **negative-authz tests passing**.

## 2. What was built
- **Security primitives** (`app/core/security.py`) — Argon2id password hashing,
  PyJWT access/refresh tokens (HS256, 30 min / 7 day), and API-key generation
  (`<prefix>.<secret>`, SHA-256 of the secret stored, full key shown once).
- **Auth dependencies** (`app/api/v1/deps.py`) — resolves a `Bearer` JWT **or**
  `X-API-Key` to a single `Principal`; `require_roles(...)` RBAC; tenant scoping
  via `ensure_customer_access`; a `rate_limit(...)` dependency.
- **Rate limiter** (`app/core/ratelimit.py`) — Redis fixed-window with
  `X-RateLimit-*` / `Retry-After` headers; **fails open** if Redis is down.
- **Error envelope** (`app/api/errors.py`) — typed `APIError` hierarchy +
  handlers rendering `{"error": {"code","message","details"}}` for app errors,
  validation errors, and HTTP errors.
- **v1 API** (`app/api/v1/`): `auth` (login/refresh/me), `operators` (onboard,
  list, issue API key, create user — platform-admin only), `customers` (list/get
  + consents + score history, tenant-scoped), `scoring`
  (**`POST /v1/score`**, **`POST /v1/score/cooperative`**, rate-limited).
- **Wiring** — `/v1` mounted; the scoring model is loaded at startup (graceful
  503 if absent); exception handlers registered.
- **OpenAPI TS client** — `scripts/export_openapi.py` dumps the schema;
  `npm run gen:api` (openapi-typescript) produces `frontend/src/lib/api/schema.ts`;
  a typed `client.ts` wraps login + score + cooperative.
- **Docs** — `docs/API.md` (auth, roles, isolation, errors, rate limits,
  endpoint table) and ADR-0022/0023.

## 3. Key decisions & trade-offs
- **ADR-0022** — dual auth (JWT + hashed API keys), Argon2 passwords, one
  `Principal` model, Redis fail-open rate limiting.
- **ADR-0023** — cross-tenant reads return **404, not 403** (no existence leak).
- **Solo-view scoping**: an operator scores its **own** customer; the pooled view
  internally enriches with other operators' repayment events — so the cooperative
  benefit is delivered without exposing other tenants' raw data.
- Deferred (documented): token revocation/blacklist, API-key rotation endpoints,
  refresh-token rotation, and per-operator policy thresholds.

## 4. File tree delta
```
backend/app/core/security.py                 (new)
backend/app/core/ratelimit.py                (new)
backend/app/core/config.py                   (model_path, decision_threshold)
backend/app/api/errors.py                    (new)
backend/app/api/v1/{__init__,deps,schemas,router}.py   (new)
backend/app/api/v1/{auth,operators,customers,scoring}.py (new)
backend/app/main.py                          (handlers, /v1, model load)
backend/tests/unit/test_ratelimit.py         (new)
backend/tests/integration/test_api.py        (new)
backend/pyproject.toml, backend/uv.lock      (pyjwt, argon2-cffi,
                                              python-multipart, fakeredis)
scripts/export_openapi.py                     (new)
frontend/openapi.json                         (generated)
frontend/src/lib/api/{schema.ts,client.ts}    (generated + typed client)
frontend/package.json (gen:api, openapi-typescript)
docs/API.md, docs/DECISIONS.md (ADR 0022-0023), README.md
```

## 5. How to run it (from a clean checkout)
```bash
cd backend && uv venv && uv pip install -e ".[dev]"
uv run python ../scripts/train_model.py     # so /v1/score works (else 503)
uv run uvicorn app.main:app --port 8000
#   Swagger UI → http://localhost:8000/docs
#   OpenAPI    → http://localhost:8000/openapi.json

# Regenerate the typed client after any API change:
uv run python ../scripts/export_openapi.py
cd ../frontend && npm install && npm run gen:api
```

## 6. How to test it (with actual results)
```bash
cd backend
uv run ruff check .   # All checks passed!
uv run black --check . # 77 files unchanged
uv run mypy           # Success: no issues found in 77 source files
uv run pytest -q      # full suite
```
**Stage 5 tests: 12 passed** (3 rate-limiter unit + 9 API integration), the API
suite against a **real Postgres + a trained model + fake Redis**. They cover:
- **login → /auth/me** (role + operator surfaced); bad password → 401.
- **unauthenticated → 401** with the error envelope.
- **tenant isolation**: operator A lists only its own customers and gets **404**
  reading operator B's customer (the negative-authz acceptance).
- **RBAC**: an operator gets **403** creating an operator; platform admin
  onboards an operator and issues an API key.
- **scoring via API key** returns a full `ScoreOut` with `X-RateLimit-*` headers.
- **`/v1/score/cooperative`** returns the **decision flip** (solo reject / pooled
  approve, pooled score > solo score).
- **OpenAPI** served with `/v1/score` + `/v1/score/cooperative` present.

Frontend: `npm run typecheck` clean against the generated client; lint/tests pass.

## 7. Screencap / demo notes
- Open **`/docs`** — the full authenticated `/v1` surface with the error envelope
  and rate-limit headers.
- `curl -s localhost:8000/openapi.json | jq '.paths | keys'` lists all 15 paths.
- The `/v1/score/cooperative` response is exactly what the Stage 7 operator
  console renders for the reject→approve money shot.

## 8. Known issues & gaps
- **No token revocation / refresh rotation** yet; logout is client-side
  (drop the token). Deferred to the Stage 9 security pass.
- **API-key management** is issue-only (no rotate/revoke endpoint yet); the
  `revoked` flag exists and is honoured.
- Rate limit is a global 60/min per principal; per-route / per-plan limits and a
  sliding window are future work.
- `python-jose` not used — PyJWT keeps the dependency surface smaller.
- mlflow/jwt emit deprecation/insecure-key warnings in tests (short test secret);
  production uses a 32-byte+ `GRIDSCORE_SECRET_KEY`.

## 9. What Stage 6 will do
**Stage 6 — Ingestion & enrichment pipeline.** Batch CSV/JSON upload of repayment
events (schema validation, dedup, per-row errors) processed by an **arq** worker;
a streaming API ingestion endpoint; **anonymisation at the boundary** (salted
identity hashing, raw identifiers never persisted, consent captured); and
**provider adapters** (mobile-money/airtime/utility ports with mock impls) feeding
an enrichment job that recomputes features — with a PII-leak test asserting no raw
identifiers reach the database.

## 10. Approval gate
**Stage 5 complete — awaiting approval to proceed.**
