# Data Model

The persistent core of GridScore AI. PostgreSQL 16, SQLAlchemy 2.0 (async) ORM,
Alembic migrations. All timestamps are UTC (`TIMESTAMPTZ`); all primary keys are
**UUIDv7** (time-ordered — see [ADR-0008](DECISIONS.md)).

> **Privacy invariant:** no raw PII is ever stored. A customer is identified only
> by a salted SHA-256 hash (`customer.identity_hash`).

## Entity-relationship overview

```
                         ┌───────────────┐
                         │   operator    │  (tenant)
                         └──────┬────────┘
        ┌───────────────┬───────┼───────────────┬────────────────┐
        │1:N            │1:N    │1:N            │1:N (RESTRICT)   │1:N
  ┌─────▼─────┐  ┌──────▼─────┐ │         ┌──────▼──────┐  ┌──────▼────────┐
  │user_account│ │api_credential│ │        │  customer   │  │ repayment_event│
  └───────────┘  └────────────┘ │        └──────┬──────┘  │  (PARTITIONED) │
                                 │   ┌───────────┼──────────┴───────┬───────┴─────┐
              requesting_operator │   │1:N        │1:N               │1:N          │1:N
                          (N:1)   │ ┌─▼──────────┐ ┌──────────────┐ ┌▼───────────┐ ┌▼──────────────┐
                                  └─┤consent_record│ │enrichment_   │ │feature_    │ │ score_result  │
                                    └────────────┘ │  signal      │ │ snapshot   │ │               │
                                                   └──────────────┘ └────────────┘ └───────────────┘
                                                                                   ┌───────────────┐
                                                   customer 1:N ───────────────────►│cooperative_lift│
                                                                                   └───────────────┘

  Platform-wide (no tenant): audit_log (immutable),  model_version
```

`repayment_event` carries **two** foreign keys — `operator_id` (which operator
contributed the row) and `customer_id` (whose history it is). That dual link is
exactly what enables the **solo view** (filter by one operator) versus the
**pooled view** (all operators) for a customer.

## Tables

| Table | Purpose | Key columns | Notable constraints |
|-------|---------|-------------|---------------------|
| `operator` | Tenant (PAYG company) | `name` (unique), `country`, `status` | enum `operator_status` |
| `user_account` | Human RBAC subject | `email` (unique), `role`, `operator_id?` | FK→operator `ON DELETE CASCADE`; `operator_id` nullable for platform/lender users |
| `api_credential` | Machine auth | `key_prefix` (unique), `hashed_secret`, `scopes[]`, `revoked` | FK→operator `CASCADE`; **only the secret hash is stored** |
| `customer` | End borrower | `identity_hash` (unique, indexed), `home_operator_id` | FK→operator `ON DELETE RESTRICT`; **no raw PII** |
| `consent_record` | Consent grants gating enrichment/scoring | `scope`, `granted`, `granted_at`, `expires_at` | FK→customer `CASCADE`; enum `consent_scope` |
| `repayment_event` | The cooperative's raw signal | `(id, due_date)` PK, `operator_id`, `customer_id`, `instalment_amount`, `status` | **range-partitioned by month on `due_date`**; FK→operator `RESTRICT`, FK→customer `CASCADE` |
| `enrichment_signal` | Mobile-money/airtime/utility data | `provider_type`, `payload_json` (JSONB), `captured_at` | FK→customer `CASCADE` |
| `feature_snapshot` | Point-in-time feature vector | `features_json` (JSONB), `view`, `computed_at` | FK→customer `CASCADE`; enum `score_view` |
| `score_result` | Audit-grade decision | `energy_credit_score`, `default_probability`, `risk_tier`, `view`, `model_version`, `explanation_json` | CHECK score ∈ [300,850], PD ∈ [0,1]; FKs→customer `CASCADE`, →operator `RESTRICT` |
| `cooperative_lift` | Materialised solo-vs-pooled diff | `solo_score`, `pooled_score`, `solo_pd`, `pooled_pd`, `lift_metric` | FK→customer `CASCADE` |
| `audit_log` | Immutable access trail | `actor`, `action`, `resource`, `metadata_json` | **append-only via DB trigger** (UPDATE/DELETE rejected) |
| `model_version` | MLflow registry mirror | `version` (unique), `mlflow_run_id`, `metrics_json`, `promoted_stage` | enum `promotion_stage` |
| `synthetic_customer_profile` | **Synthetic-only** generator ground truth | `customer_id` (unique), `default_label`, `default_probability_true`, `latent_features_json`, `is_demo`, `scenario` | FK→customer `CASCADE`; **empty in production** (added in migration 0002) |

Enum types (native PostgreSQL `ENUM`): `operator_status`, `user_role`,
`user_status`, `consent_scope`, `repayment_status`, `provider_type`,
`score_view`, `risk_tier`, `promotion_stage`. Stored values are the lowercase
StrEnum *values* (e.g. `on_time`), not Python member names.

## Partitioning strategy — `repayment_event`

This is the highest-volume table (every instalment for every customer at every
operator), so it is **declaratively range-partitioned by month** on `due_date`.

- **Why month / `due_date`:** repayment analytics and feature windows are
  time-bounded ("last N months"), so month partitions enable *partition pruning*
  — queries touch only relevant months. Time-series retention/archival becomes a
  cheap `DETACH PARTITION` instead of a mass `DELETE`.
- **Composite PK `(id, due_date)`:** PostgreSQL requires the partition key to be
  part of every unique constraint, so the natural `id` PK is extended with
  `due_date`.
- **Child partitions:** the initial migration creates **48 monthly partitions**
  (Jan 2023 → Dec 2026) plus a **`DEFAULT`** catch-all so inserts outside the
  window never fail. In production a scheduled maintenance job (Stage 6 worker;
  or `pg_partman`) rolls the window forward and detaches aged partitions.
- **Indexes** are created on the *parent* and automatically propagate to every
  partition.

## Indexing plan (hot lookups)

| Index | Columns | Rationale |
|-------|---------|-----------|
| `ix_customer_identity_hash` (unique) | `customer.identity_hash` | The cooperative's primary join key: "do we already know this person?" on every ingestion and score. |
| `ix_repayment_event_customer_id_due_date` | `(customer_id, due_date)` | Pooled/solo history reads and time-windowed feature builds; supports pruning + ordering. |
| `ix_repayment_event_operator_id` | `operator_id` | Solo-view filtering and per-operator analytics. |
| `ix_repayment_event_status` | `status` | Default-rate aggregations. |
| `ix_score_result_customer_id` | `score_result.customer_id` | Score history lookups. |
| `ix_*_customer_id` | consent/enrichment/feature/lift `customer_id` | Per-customer fan-out reads. |
| `ix_user_account_operator_id`, `ix_api_credential_operator_id` | tenant FKs | Tenant-scoped access. |
| unique: `operator.name`, `user_account.email`, `api_credential.key_prefix`, `model_version.version` | — | Natural-key integrity. |

## Layering & transactions

- **Models** (`app/db/models/`) define the schema; **repositories**
  (`app/db/repositories/`) are the only place queries are issued; **services**
  (later stages) depend on repositories, never on the session.
- The `get_session` dependency owns the transaction boundary (commit on success,
  rollback on error). Repositories `flush` but never `commit`.
- Parent→child deletes use `passive_deletes` so the database's `ON DELETE
  CASCADE`/`RESTRICT` rules are authoritative (the ORM never nulls a NOT NULL FK,
  and large `repayment_event` sets are never loaded into memory just to delete).

## Migrations

Single initial migration `0001_initial`. Standard tables are created from
`Base.metadata` (one source of truth, no model/migration drift); the partitioned
`repayment_event`, its partitions, and the audit-log immutability trigger use
explicit SQL. Verified to **apply to an empty DB and fully roll back** (see the
Stage 1 report and `tests/integration/test_migrations.py`).
