# Roadmap

Where GridScore is and what a production build would add. This is a **prototype on
synthetic data**: the architecture, privacy model, cooperative economics, and the
two proof artifacts (the decision flip and the network-effect chart) are real and
in the code — but several things a live credit bureau needs are deliberately
deferred and listed here honestly rather than hidden.

## Where it stands (Stages 0–10, complete)
- Multi-tenant `/v1` API (JWT + hashed API keys, RBAC, per-operator isolation).
- Batch/stream ingestion with boundary anonymisation (salted SHA-256; raw PII
  never stored), consent gating, and an immutable audit log.
- XGBoost + isotonic calibration + SHAP scoring; the **cooperative lift** (solo vs
  pooled) and the **AUC-vs-operators** network-effect measurement.
- Operator console, lender/DFI analytics, platform admin (React/TS).
- Observability (Prometheus/OTel/structured logs), a data-retention purge, a
  security pass (OWASP checklist, dependency audit), CI, and deploy blueprints
  (Render + Vercel / docker-compose.prod).

## Deferred to a production build

### Data & modelling
- **Real data onboarding**: partner data-sharing agreements, per-operator schema
  mapping, and a validation/quarantine lane. Replace synthetic generation with
  real repayment feeds; re-establish the AUC ceiling on real labels.
- **Model lifecycle**: scheduled retraining, champion/challenger and shadow
  scoring, drift-triggered retrain (the drift module exists; wire it to alerts),
  and a model-approval workflow before promotion.
- **Fairness & regulation**: subgroup performance and adverse-action reporting,
  bias testing, and reason codes that satisfy local consumer-credit regulation.

### Privacy, security & compliance
- Refresh-token rotation + revocation list; account lockout / brute-force
  throttling on login; API-key rotation endpoint (the `revoked` flag is honoured).
- Field-level encryption at rest for enrichment payloads; **KMS-managed** identity
  salt with a rotation story (rotating the salt today re-buckets identities).
- Data-subject rights (access/erasure) beyond the retention purge; a documented
  legal basis and consent ledger; SOC2-style controls; WAF / edge rate limiting.

### Platform & operations
- Real provider integrations (mobile-money, telco, utility) behind the existing
  ports — currently mocked adapters.
- OTLP trace export to Tempo/Jaeger + Grafana dashboards and alerting (dev uses the
  console exporter); SLOs and on-call runbooks.
- HA Postgres (replicas, PITR backups) and Redis; blue-green / canary releases;
  load/soak testing beyond the in-process benchmark and Locust file.
- Billing/metering for operators and lenders; a self-serve onboarding flow.

### Dependencies
- Bump **Starlette to ≥1.x** once FastAPI supports it, to clear the residual
  advisories logged in `docs/SECURITY.md`; upgrade `mlflow`/`pyarrow`.

## Explicitly out of scope for the prototype
- Serving real credit decisions to real borrowers.
- Any storage of raw PII (this is a hard design invariant, not a TODO).
- Cross-border data-residency guarantees.
