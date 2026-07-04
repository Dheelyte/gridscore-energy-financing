# Security

> Security posture for GridScore AI. This is a pre-production prototype on
> **synthetic data**; this document records the controls that exist in code and
> the items deliberately deferred to a production hardening phase.

## Authentication & authorisation
- **Human users**: OAuth2 password flow → short-lived JWT access (30 min) +
  refresh (7 days), HS256 (`app/core/security.py`).
- **Machine clients**: API keys `<prefix>.<secret>`; only the **SHA-256 of the
  secret** is stored; the full key is shown once.
- **Passwords**: Argon2id (memory-hard).
- **RBAC** per route (`require_roles`); **tenant isolation** (`ensure_customer_access`)
  returns **404** cross-tenant so existence is not leaked (ADR-0023).
- Tested: negative-authz (operator → admin/lender routes = 403; cross-tenant
  reads + subresources = 404) including a parametrised authz-fuzz.

## Secrets handling
- All secrets come from the environment (`pydantic-settings`, `GRIDSCORE_`
  prefix); typed as `SecretStr` so they never appear in logs / `repr`.
- Nothing secret is committed; `.env.example` holds placeholders only; `.env`,
  keys, and `secrets.*` are git-ignored.
- Production must set a ≥32-byte `GRIDSCORE_SECRET_KEY` and a strong
  `GRIDSCORE_IDENTITY_HASH_SALT`.

## Privacy
- **No raw PII** is ever stored — identities are a salted SHA-256 computed at the
  ingestion boundary; a PII-leak test asserts the raw value never reaches the DB.
- **Consent** gates enrichment and scoring; refusals are audited.
- **Immutable audit log** (DB trigger rejects UPDATE/DELETE) for every score and
  data access.
- **Data-retention purge** (`app/services/retention.py`, nightly arq cron)
  deletes derived artefacts (feature snapshots, scores, lifts) older than
  `GRIDSCORE_RETENTION_DAYS`; the audit log is retained.

## Rate limiting & availability
- Redis fixed-window limiter per principal on scoring/ingestion routes, with
  `X-RateLimit-*` / `Retry-After` headers; **fails open** if Redis is down.

## Transport & platform (deployment responsibilities)
- TLS terminates at the platform (Render/Vercel/ingress); HSTS there.
- CORS origins are configured via `GRIDSCORE_CORS_ORIGINS`.

## OWASP Top-10 (2021) checklist

| # | Category | Status | Notes |
|---|----------|--------|-------|
| A01 | Broken Access Control | ✅ | RBAC + tenant isolation (404 cross-tenant); authz-fuzz tests. |
| A02 | Cryptographic Failures | ✅ | Argon2id passwords; API secrets hashed (SHA-256); JWT HS256; SecretStr. |
| A03 | Injection | ✅ | SQLAlchemy parameterised queries only; Pydantic-validated input; no string SQL with user data. |
| A04 | Insecure Design | ✅ | Hexagonal layering, consent gating, immutable audit, idempotent ingestion. |
| A05 | Security Misconfiguration | ⚠️ | Twelve-factor config; consistent error envelope (no stack traces leaked). Prod must set strong secrets + TLS/HSTS at the edge. |
| A06 | Vulnerable Components | ⚠️ | `pip-audit` CI job (non-blocking, see below); pins recorded; transitive advisories triaged. |
| A07 | Identification & Auth Failures | ✅ | Strong password hashing, token expiry, hashed API keys. **Deferred**: refresh-token rotation, token revocation list, lockout. |
| A08 | Software & Data Integrity | ✅ | Lockfiles committed; OpenAPI-generated client prevents contract drift; model card from the actual run. |
| A09 | Logging & Monitoring Failures | ✅ | Structured logs + correlation IDs, Prometheus `/metrics`, OTel traces, immutable audit log. |
| A10 | SSRF | ✅ | No user-controlled outbound requests; provider adapters are mocks behind ports. |

## Dependency audit
`pip-audit` runs against the locked environment as a **non-blocking CI job**
(advisories are triaged here rather than failing the build). Findings as of the
Stage 9 pass, with disposition:

- **starlette** (runtime, under FastAPI) — **partially addressed**: bumped
  `fastapi` 0.115 → 0.120 and `starlette` 0.46 → **0.49.3** (the newest FastAPI
  supports), which clears several advisories. The remaining ones list fixes only
  in **starlette ≥1.x**, which FastAPI does not yet support — **logged**, to be
  bumped when FastAPI moves to starlette 1.x. App + full test suite verified on
  the new versions.
- **mlflow, pyarrow** (ML tooling) — advisories present; training-time only, not
  on the request path. Tracked for upgrade.
- **pytest** (dev only) — advisory; dev-time only.

npm `audit` flagged transitive **dev-tooling** advisories at scaffold time (same
disposition). The CI `pip-audit` job documents the current state on every run.

## Deferred to production hardening
- Refresh-token rotation + revocation list; account lockout / brute-force
  throttling on `/auth/login`.
- API-key rotation endpoint (the `revoked` flag exists and is honoured).
- Field-level encryption at rest for enrichment payloads; KMS-managed salt.
- WAF / edge rate limiting; full SOC2-style controls.
