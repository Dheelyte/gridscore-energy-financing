# API Reference (v1)

The versioned `/v1` REST API. Served live as OpenAPI at `/openapi.json` and
Swagger UI at `/docs`. A typed TypeScript client is generated from the schema
(`frontend/src/lib/api/schema.ts`, via `npm run gen:api`).

## Authentication

Two schemes resolve to one principal:

| Scheme | Header | Used by |
|--------|--------|---------|
| JWT (OAuth2 password flow) | `Authorization: Bearer <access_token>` | human users |
| API key | `X-API-Key: <prefix>.<secret>` | machine clients (operators) |

Access tokens last 30 min; refresh tokens 7 days. API keys are stored as a
SHA-256 of the secret; the full key is shown **once** at issuance.

### Roles (RBAC)
`platform_admin` (cross-tenant), `operator_admin`, `operator_analyst`,
`lender_viewer`. API-key principals act as `operator_analyst` for their operator.

### Tenant isolation
Operators may only read their **own** customers (and their derived data). A
cross-tenant read returns **404** (existence is not leaked). `platform_admin` is
unrestricted.

## Error envelope

Every error has the shape:

```json
{ "error": { "code": "forbidden", "message": "Insufficient role.", "details": {} } }
```

Codes: `unauthenticated` (401), `forbidden` (403), `not_found` (404),
`conflict` (409), `validation_error` (422), `rate_limited` (429),
`service_unavailable` (503).

## Rate limiting

Scoring endpoints are rate-limited per principal (default 60 req/min, Redis
fixed-window). Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
`X-RateLimit-Reset`; a 429 adds `Retry-After`. Fails open if Redis is down.

## Endpoints

| Method | Path | Auth / role | Description |
|--------|------|-------------|-------------|
| POST | `/v1/auth/login` | public | OAuth2 password login → tokens |
| POST | `/v1/auth/refresh` | refresh token | new access + refresh tokens |
| GET | `/v1/auth/me` | any principal | current identity |
| POST | `/v1/operators` | platform_admin | onboard an operator |
| GET | `/v1/operators` | platform_admin | list operators |
| POST | `/v1/operators/{id}/api-keys` | platform_admin | issue a machine API key |
| POST | `/v1/operators/users` | platform_admin | create a user account |
| GET | `/v1/customers` | operator/admin | list own customers |
| GET | `/v1/customers/{id}` | operator/admin | get a customer (tenant-scoped) |
| GET | `/v1/customers/{id}/consents` | operator/admin | consent records |
| POST | `/v1/customers/{id}/consents` | operator/admin | record consent |
| GET | `/v1/customers/{id}/scores` | operator/admin | score history |
| POST | `/v1/score` | operator + key | score (solo or pooled) |
| POST | `/v1/score/cooperative` | operator + key | **cooperative lift + decision flip** |

### `POST /v1/score/cooperative`
Request: `{ "customer_id": "<uuid>" }`. Response includes `solo` and `pooled`
`ScoreOut` objects plus `pd_delta`, `confidence_delta`, `score_delta`,
`decision_flips`, and `lift_metric` — the on-screen proof of the cooperative
network effect.

## Regenerating the client
```bash
python scripts/export_openapi.py        # writes frontend/openapi.json
cd frontend && npm run gen:api          # writes src/lib/api/schema.ts
```
