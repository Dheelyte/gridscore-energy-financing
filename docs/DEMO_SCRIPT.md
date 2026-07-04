# Demo Script — the 3-minute GridScore walkthrough

> A precise, timed walkthrough for the pitch. Everything here runs on **synthetic
> data** (labelled synthetic in the DB). Two artifacts carry the story:
> **(1)** the per-customer **reject → approve decision flip** (Stage 7) and
> **(2)** the **AUC-vs-operators network-effect chart** (Stage 8). One demonstrates
> the cooperative's value for a single borderline borrower; the other demonstrates
> it in aggregate.

## The one number to remember

The curated borderline customer has a **stable identity hash** (independent of the
deployment salt, so it is always the same):

```
e5d859ae716c3734cf635a777919f0a0996d713a36dea43fb611ab424e2838d9
```

- **Solo view** (home operator only): 3 recent instalments, 2 late →
  **~33% on-time, ~3 months of history** → thin-file + unlucky → **REJECT**.
- **Pooled view** (full cooperative): +25 on-time instalments from other operators
  → **~93% on-time, ~28 months** → clearly reliable → **APPROVE**.
- The customer is *genuinely* reliable (true PD ≈ 0.06). The solo lender simply
  can't see it. **That gap is the product.**

## Pre-flight (before you present)

```bash
# 1. Stack up (local) and migrated
docker compose -f infra/docker-compose.yml up --build -d
# 2. Seed the synthetic scenario (includes the borderline customer above)
cd backend && GRIDSCORE_DATABASE_URL=postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore \
  uv run python ../scripts/seed_demo.py         # note the printed demo customer + AUC ceiling
# 3. The seed also creates demo logins (printed at the end). For the flip, use:
#      analyst@gridscore.ai  /  GridScore!Demo1   (operator_analyst)
#    Also available: admin@gridscore.ai (platform_admin),
#    lender@gridscore.ai (lender_viewer) — same password. See RUNBOOK.
```
Confirm before going live: the frontend loads, you are logged in, and the demo
customer's hash is on your clipboard. Have the analytics page pre-opened in a
second tab so the chart is warm.

## Timed script (~3:00)

### 0:00–0:30 — The problem (title + one slide)
"PAYG solar and appliance lenders in Africa each hold a thin, siloed repayment
history per customer. A good borrower who is new to *you* looks identical to a
risky one. So lenders reject people who would have repaid — and the whole market
under-lends." Cut to the app.

### 0:30–1:40 — The decision flip (the money shot)
1. Operator console → **look up the borderline customer** by the hash above.
2. Show the **solo** score first: the gauge sits in the reject band; the panel
   reads ~33% on-time over ~3 months. "On our own data, we decline this person."
3. Toggle to the **pooled cooperative** view. The **same customer**: the gauge
   swings up into the approve band; on-time jumps to ~93% over ~28 months.
   **"Same person, same instant — reject becomes approve, because the cooperative
   fills in the history we never had."**
4. Point at the **SHAP explanation**: the features that moved are the pooled
   repayment-rate and history-length — *not* enrichment. The flip is earned by the
   shared repayment signal, not a black box.

### 1:40–2:35 — It's not a fluke: the network effect
1. Analytics page → the **AUC-vs-operators chart**. As operators join the pool,
   held-out **AUC climbs** (roughly **0.69 → 0.74** in the seeded run — realistic,
   not suspiciously perfect).
2. "Every operator who joins makes *everyone's* model better. That's a data
   network effect, and it's why this is infrastructure, not a feature." Mention the
   base default rate (~10–20%) and the honest AUC ceiling the seed prints.

### 2:35–3:00 — Why it's trustworthy / close
"Raw national IDs and phone numbers are never stored — only salted hashes computed
at ingestion. Every score and access is written to an immutable audit log, scoring
is consent-gated, and it's multi-tenant with per-operator isolation. This is a
prototype on synthetic data — but the privacy, the audit trail, and the
cooperative economics are real and in the code." End on the flip screen.

## If you have 60 extra seconds (backup beats)
- **Platform admin**: show the operator roster + network-effect summary.
- **Audit log**: filter to the demo customer — every score attempt is there.
- **/metrics + request IDs**: the same request correlates across logs, traces, and
  the response header (Stage 9).
- **Consent revoked**: scoring is refused and the refusal is audited.

## Honesty guardrails (say these out loud)
- The data is **synthetic** and labelled as such; numbers are illustrative.
- AUC is deliberately in the **realistic 0.70–0.82** range — a suspiciously high
  AUC would signal target leakage, which the training pipeline actively guards
  against.
- The borderline customer is **curated** to make the mechanism legible; the
  aggregate chart is what shows it holds at scale.

## Recovery (if something breaks live)
- Customer not found → re-run `seed_demo.py`; the hash above is deterministic.
- Chart empty → the network-effect job hasn't run; trigger it from analytics or
  restart the worker (`docker compose ... up -d worker`).
- API offline banner → check `VITE_API_BASE_URL` and that `api` is healthy
  (`/health`).
