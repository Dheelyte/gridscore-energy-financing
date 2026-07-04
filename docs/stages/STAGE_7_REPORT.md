# Stage 7 Report — Operator Console (Frontend)

## 1. Stage name & objective
**Stage 7 — Operator console.** The screen-recorded dashboard: an auth flow and
role-aware app shell, customer score lookup (score gauge, default probability,
risk tier, SHAP top factors), the **cooperative panel** — the centrepiece — with
an animated solo-vs-pooled reveal and the **reject → approve decision flip** on
the borderline customer, a portfolio overview, and a data-upload UI wired to the
Stage 6 ingestion API. Built on the generated, typed OpenAPI client so the SPA
and backend cannot drift. Acceptance: a human logs in, looks up the borderline
customer, and watches the pooled view flip the decision against the live backend.

## 2. What was built
- **Typed API client** (`src/lib/api/client.ts`) over the generated
  `schema.ts` — login, me, customers, score, cooperative, ingest, portfolio.
- **Auth** (`src/lib/auth.tsx`) — token persistence, `me` bootstrap, login/logout;
  `RequireAuth` guard; role-aware app shell with nav and a role badge.
- **Routing/providers** — React Router + TanStack Query + an auth provider; the
  marketing landing stays at `/`, console under `/console|/portfolio|/upload`.
- **Score view** — an animated SVG `ScoreGauge` (300–850, tier-coloured), a
  `ScoreCard` with PD + decision, and `TopFactors` (SHAP bars, red = increases /
  green = decreases risk).
- **Cooperative panel** (`CooperativePanel`) — side-by-side solo vs pooled,
  revealed on "Pool the cooperative" with a transition, the PD/score/confidence
  lift, and a prominent **Reject → Approve** flip banner.
- **Operator console page** — searchable customer list (+ a "Borderline demo
  customer" jump that computes the demo identity hash client-side), score + SHAP,
  and the cooperative panel.
- **Upload page** — JSON event ingestion wired to `POST /v1/ingest/events`, with a
  validated report (inserted / duplicates / failed / enriched) and per-row errors.
- **Portfolio page** — KPIs (customers, scored, approval rate, **est. losses
  avoided**) and a Recharts risk-tier donut, from a new
  **`GET /v1/portfolio/summary`** that aggregates real `score_result` rows.
- **Backend** — the portfolio summary endpoint (latest score per customer,
  tier mix, approval rate, losses-avoided heuristic) wired into `/v1`.

## 3. Key decisions & trade-offs
- **Generated client, hand-rolled fetch wrapper** — types come from OpenAPI
  (`npm run gen:api`); a thin `fetch` wrapper adds auth + the error envelope. No
  heavy client runtime.
- **Animation via CSS transitions** (not a motion library) — keeps deps light
  while still delivering the reveal/flip "money shot".
- **Operator portfolio from real aggregates** — `score_result` rows, not
  hard-coded; an empty state when nothing is scored yet. Cross-operator lender
  analytics + the network-effect chart remain Stage 8.
- Bundle is a single ~645 kB chunk (recharts + router + query); code-splitting is
  a deliberate later optimisation (noted).

## 4. File tree delta
```
frontend/src/lib/{api/client.ts,auth.tsx,demo.ts,utils.ts}
frontend/src/components/{ScoreGauge.tsx, ui/{card,badge,input,button}.tsx}
frontend/src/features/auth/LoginPage.tsx
frontend/src/features/scoring/{ScoreCard,TopFactors,CooperativePanel}.tsx (+ tests)
frontend/src/features/console/OperatorConsolePage.tsx
frontend/src/features/ingest/UploadPage.tsx
frontend/src/features/portfolio/PortfolioPage.tsx
frontend/src/app/{Routes,AppShell,RequireAuth,providers}.tsx, main.tsx, App.tsx
frontend/{playwright.config.ts, e2e/console.spec.ts, vite.config.ts}
frontend/package.json (react-router, tanstack-query, recharts, playwright)
backend/app/api/v1/portfolio.py (+ router wiring) + test_api.py (portfolio)
frontend/openapi.json, src/lib/api/schema.ts (regenerated, 19 paths)
```

## 5. How to run it (from a clean checkout)
```bash
# Backend (seed + model so scoring/portfolio work):
cd backend && uv pip install -e ".[dev]"
uv run python ../scripts/train_model.py
docker compose -f ../infra/docker-compose.yml up -d postgres redis
GRIDSCORE_DATABASE_URL=postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore \
  uv run alembic upgrade head
uv run python ../scripts/seed_demo.py        # seeds the borderline customer + operators
uv run uvicorn app.main:app --port 8000

# Frontend:
cd frontend && npm install && npm run dev     # http://localhost:5173
#   Log in as the seeded operator admin → Console → "Borderline demo customer"
#   → "Pool the cooperative" → watch Reject → Approve.
```

## 6. How to test it (with actual results)
```bash
cd frontend
npm run typecheck   # tsc clean
npm run lint        # 0 errors (1 pre-existing react-refresh warning)
npm test            # Vitest
npm run build       # vite build OK
npm run e2e         # Playwright (mocks the API; runs the login→flip flow)
```
**Vitest: 6 passed** — including `CooperativePanel` asserting the pooled reveal
and the **reject→approve** flip banner, and `ScoreCard` rendering the score/PD/
SHAP factors. **Playwright e2e: 1 passed** (chromium, ~20 s) — login → console →
reveal the reject→approve flip in a real browser (hermetic via request mocking;
the same flow runs against a live seeded backend). Backend: a new
`test_portfolio_summary_reflects_scores` integration test covers the portfolio
endpoint.

## 7. Screencap / demo notes (for the pitch video)
1. **Login** as the operator admin → land on the **Console**.
2. Click **"Borderline demo customer"** → the pooled `ScoreCard` shows an
   approve with the SHAP factors (PAYG repayment rate on top).
3. In the **Cooperative panel**, the **Solo view** shows a **Reject** (tier E,
   ~536). Click **"Pool the cooperative"** — the pooled column sweeps in (tier B,
   ~655), the lift metrics appear, and the **Reject → Approve** banner lands.
   *This is the money shot.*
4. **Portfolio** tab → risk-tier donut + "losses avoided"; **Upload data** tab →
   paste events → see the live ingestion report.

## 8. Known issues & gaps
- **Single JS bundle (~645 kB)** — recharts/query/router; code-splitting deferred.
- The Playwright e2e uses **request mocking** for hermetic CI; an against-live
  variant needs the seeded backend running (documented).
- Portfolio "losses avoided" is a **documented heuristic** ($200 representative
  loan × PD over declined customers), not a financial model — Stage 8 refines the
  lender-facing figures.
- No customer **search by raw identifier** (privacy: only hashes are stored); the
  UI searches the hash and offers the demo-customer jump.

## 9. What Stage 8 will do
**Stage 8 — Lender/DFI analytics + platform admin console.** Portfolio-level risk
across funded operators with an "additional debt capacity unlocked" estimate; a
platform-admin console (operator onboarding, API-key issuance, cooperative health,
model registry, audit-log search); and the **AUC-vs-operators network-effect
chart** computed by retraining on increasing operator subsets — the empirical
moat, not a hard-coded line.

## 10. Approval gate
**Stage 7 complete — awaiting approval to proceed.**
