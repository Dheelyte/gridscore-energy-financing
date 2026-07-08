/**
 * Fully client-side mock of the GridScore backend.
 *
 * Swapped in for the real {@link api} when `VITE_USE_MOCK` is not `"false"` (see
 * `client.ts`), so the app is a complete, self-contained demo on Vercel with no
 * backend deployed. Every value is SYNTHETIC and deterministic: the same seed
 * produces the same population, scores, and portfolio aggregates each load, and
 * all headline numbers (approval rate, tier mix, losses avoided, network effect)
 * are computed from that one population so they stay internally consistent.
 *
 * The curated borderline demo customer still flips reject → approve between the
 * solo and pooled views — the core pitch — exactly as the seeded backend does.
 */
import { demoIdentityHash } from "../demo";
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "../demoAccounts";

import {
  ApiError,
  getAccessToken,
  setAccessToken,
  type ActiveModel,
  type AuditEntry,
  type CooperativeOut,
  type Customer,
  type Health,
  type IngestEvent,
  type IngestResponse,
  type Me,
  type NetworkEffect,
  type PortfolioAnalytics,
  type PortfolioSummary,
  type ScoreOut,
  type ScoreView,
  type Token,
} from "./client";

// ---- decision policy (mirrors backend GRIDSCORE_DECISION_THRESHOLD default) ----
const THRESHOLD = 0.12;
const AVG_LOAN_USD = 420;

// ---- tiny deterministic PRNG so every reload yields the same demo ----
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seedFromString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function hex(rng: () => number, len: number): string {
  let out = "";
  while (out.length < len) out += Math.floor(rng() * 16).toString(16);
  return out.slice(0, len);
}

function uuidFrom(rng: () => number): string {
  const h = hex(rng, 32);
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`;
}

const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi);
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---- scoring maths ----
function tierFor(pd: number): "A" | "B" | "C" | "D" | "E" {
  if (pd < 0.05) return "A";
  if (pd < 0.1) return "B";
  if (pd < 0.18) return "C";
  if (pd < 0.3) return "D";
  return "E";
}

function scoreFor(pd: number): number {
  // Monotonic 850 (pd 0) → 300 (pd 0.45+), matching the ScoreGauge 300–850 range.
  return clamp(Math.round(850 - (pd / 0.45) * 550), 300, 850);
}

const FACTORS: { feature: string; label: string; decreases: boolean; pooledOnly?: boolean }[] = [
  { feature: "on_time_rate", label: "On-time repayment rate", decreases: true },
  { feature: "coop_history_depth", label: "Cooperative history depth", decreases: true, pooledOnly: true },
  { feature: "account_tenure", label: "Account tenure", decreases: true },
  { feature: "recent_late", label: "Recent late instalments", decreases: false },
  { feature: "mm_inflow_vol", label: "Mobile-money inflow volatility", decreases: false },
  { feature: "region_default", label: "Region base default rate", decreases: false },
];

function topFactorsFor(customerId: string, view: ScoreView, pd: number): ScoreOut["top_factors"] {
  const rng = mulberry32(seedFromString(`${customerId}:${view}`));
  const factors = FACTORS.map((f) => {
    let mag = 0.03 + rng() * 0.3;
    // The pooled view's defining signal: cooperative history depth is a strong
    // risk-reducer that the solo view simply cannot see.
    if (f.feature === "coop_history_depth") mag = view === "pooled" ? 0.34 + rng() * 0.1 : 0.02;
    const contribution = f.decreases ? -mag : mag;
    return {
      feature: f.feature,
      label: f.label,
      value: Math.round((f.decreases ? 1 - pd : pd) * 100) / 100,
      contribution: Math.round(contribution * 100) / 100,
      direction: f.decreases ? "decreases" : "increases",
    };
  });
  return factors.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 5);
}

// ---- synthetic population (generated once, reused for every aggregate) ----
interface PopCustomer extends Customer {
  soloPd: number;
  pooledPd: number;
}

const OPERATORS = (() => {
  const names = [
    "Sunlight PAYG (KE)",
    "Azuri Metro (NG)",
    "Bboxx Rift (RW)",
    "d.light Coast (TZ)",
    "Zola Central (GH)",
    "Greenlight Sahel (SN)",
  ];
  const rng = mulberry32(101);
  return names.map((name) => ({ id: uuidFrom(rng), name }));
})();

const OPERATOR_WEIGHTS = [0.28, 0.22, 0.18, 0.14, 0.1, 0.08];
const CUSTOMER_COUNT = 2000;

function pickOperator(u: number): number {
  let acc = 0;
  for (let i = 0; i < OPERATOR_WEIGHTS.length; i++) {
    acc += OPERATOR_WEIGHTS[i];
    if (u <= acc) return i;
  }
  return OPERATOR_WEIGHTS.length - 1;
}

let populationPromise: Promise<PopCustomer[]> | null = null;

async function population(): Promise<PopCustomer[]> {
  if (populationPromise) return populationPromise;
  populationPromise = (async () => {
    const demoHash = await demoIdentityHash();
    const rng = mulberry32(20240704);
    const now = Date.now();
    const customers: PopCustomer[] = [];

    for (let i = 0; i < CUSTOMER_COUNT; i++) {
      const opIdx = pickOperator(rng());
      // Skewed toward low PD (many bankable), with a long risky tail; mean ~0.14.
      const pooledPd = clamp(0.02 + Math.pow(rng(), 3) * 0.5, 0.01, 0.6);
      // Solo (home-operator-only) always looks a little riskier — less data.
      const soloPd = clamp(pooledPd * (1.12 + rng() * 0.35), 0.01, 0.72);
      customers.push({
        id: uuidFrom(rng),
        identity_hash: hex(rng, 64),
        home_operator_id: OPERATORS[opIdx].id,
        created_at: new Date(now - Math.floor(rng() * 540) * 86_400_000).toISOString(),
        soloPd,
        pooledPd,
      });
    }

    // The curated borderline customer: solo → reject (PD 0.16), pooled → approve
    // (PD 0.07). Belongs to the largest operator, like the seeded backend.
    customers[0] = {
      ...customers[0],
      identity_hash: demoHash,
      home_operator_id: OPERATORS[0].id,
      soloPd: 0.16,
      pooledPd: 0.07,
    };
    return customers;
  })();
  return populationPromise;
}

function scoreOut(c: PopCustomer, view: ScoreView): ScoreOut {
  const pd = view === "pooled" ? c.pooledPd : c.soloPd;
  return {
    customer_id: c.id,
    view,
    default_probability: Math.round(pd * 10000) / 10000,
    energy_credit_score: scoreFor(pd),
    risk_tier: tierFor(pd),
    approved: pd < THRESHOLD,
    model_version: "v3",
    top_factors: topFactorsFor(c.id, view, pd),
  };
}

async function findCustomer(customerId: string): Promise<PopCustomer> {
  const pop = await population();
  const c = pop.find((x) => x.id === customerId);
  if (!c) throw new ApiError(404, "not_found", "Customer not found");
  return c;
}

// ---- session token: encode identity into the fake bearer token ----
function decodeSession(): { role: Me["role"]; email: string } | null {
  const token = getAccessToken();
  if (!token || !token.startsWith("mock.")) return null;
  const [, role, email] = token.split(".");
  return { role: role as Me["role"], email: email ? atob(email) : "" };
}

const OPERATOR_SUBJECT = uuidFrom(mulberry32(7));

export const mockApi = {
  async login(email: string, password: string): Promise<Token> {
    await delay(280);
    if (password !== DEMO_PASSWORD) {
      throw new ApiError(401, "invalid_credentials", "Invalid email or password");
    }
    const known = DEMO_ACCOUNTS.find((a) => a.email === email);
    const role = (known?.role ?? "operator_analyst") as Me["role"];
    const token: Token = {
      access_token: `mock.${role}.${btoa(email)}`,
      refresh_token: `mock-refresh.${role}`,
      token_type: "bearer",
    };
    setAccessToken(token.access_token);
    return token;
  },

  async me(): Promise<Me> {
    await delay(120);
    const session = decodeSession();
    if (!session) throw new ApiError(401, "unauthenticated", "Not signed in");
    return {
      kind: "user",
      subject_id: OPERATOR_SUBJECT,
      role: session.role,
      operator_id: session.role === "operator_analyst" ? OPERATORS[0].id : null,
      email: session.email,
    };
  },

  async listCustomers(): Promise<Customer[]> {
    await delay(260);
    const pop = await population();
    // Demo customer first, then the rest — strip the private PD fields.
    return pop.map(({ soloPd: _s, pooledPd: _p, ...c }) => c);
  },

  async score(customerId: string, view: ScoreView = "pooled"): Promise<ScoreOut> {
    await delay(320);
    return scoreOut(await findCustomer(customerId), view);
  },

  async scoreCooperative(customerId: string): Promise<CooperativeOut> {
    await delay(340);
    const c = await findCustomer(customerId);
    const solo = scoreOut(c, "solo");
    const pooled = scoreOut(c, "pooled");
    const pd_delta = Math.round((c.soloPd - c.pooledPd) * 10000) / 10000;
    return {
      customer_id: c.id,
      solo,
      pooled,
      pd_delta,
      confidence_delta: clamp(Math.round((pd_delta * 1.5 + 0.05) * 100) / 100, 0, 1),
      score_delta: pooled.energy_credit_score - solo.energy_credit_score,
      decision_flips: !solo.approved && pooled.approved,
      lift_metric: Math.round((pd_delta / Math.max(c.soloPd, 0.001)) * 100) / 100,
    };
  },

  async portfolio(): Promise<PortfolioSummary> {
    await delay(260);
    const pop = await population();
    const tiers: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, E: 0 };
    let approved = 0;
    let pdSum = 0;
    let lossesAvoided = 0;
    for (const c of pop) {
      tiers[tierFor(c.pooledPd)]++;
      if (c.pooledPd < THRESHOLD) approved++;
      pdSum += c.pooledPd;
      lossesAvoided += (c.soloPd - c.pooledPd) * AVG_LOAN_USD;
    }
    return {
      total_customers: pop.length,
      scored_customers: pop.length,
      tier_distribution: tiers,
      approval_rate: approved / pop.length,
      average_default_probability: pdSum / pop.length,
      estimated_losses_avoided_usd: Math.round(lossesAvoided),
    };
  },

  async lenderPortfolio(): Promise<PortfolioAnalytics> {
    await delay(300);
    const pop = await population();
    const tiers: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, E: 0 };
    const buckets = [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5];
    const hist = buckets.slice(0, -1).map((from, i) => ({ from, to: buckets[i + 1], count: 0 }));
    const byOperator: Record<string, number> = {};
    let approved = 0;
    let pdSum = 0;
    let newlyBankable = 0;
    for (const c of pop) {
      tiers[tierFor(c.pooledPd)]++;
      if (c.pooledPd < THRESHOLD) approved++;
      if (c.pooledPd < THRESHOLD && c.soloPd >= THRESHOLD) newlyBankable++;
      pdSum += c.pooledPd;
      byOperator[c.home_operator_id] = (byOperator[c.home_operator_id] ?? 0) + 1;
      const b = hist.find((h) => c.pooledPd >= h.from && c.pooledPd < h.to) ?? hist[hist.length - 1];
      b.count++;
    }
    const concentration = OPERATORS.map((o) => ({
      operator: o.name,
      share: (byOperator[o.id] ?? 0) / pop.length,
    })).sort((a, b) => b.share - a.share);
    return {
      scored_customers: pop.length,
      average_default_probability: pdSum / pop.length,
      approval_rate: approved / pop.length,
      pd_histogram: hist,
      tier_distribution: tiers,
      operator_concentration: concentration,
      newly_bankable_customers: newlyBankable,
      estimated_debt_capacity_unlocked_usd: newlyBankable * AVG_LOAN_USD,
    };
  },

  async networkEffect(): Promise<NetworkEffect> {
    await delay(600);
    // Empirical-looking rising ROC-AUC as operators pool their histories.
    const points = [
      { operators: 1, auc: 0.642 },
      { operators: 2, auc: 0.694 },
      { operators: 3, auc: 0.729 },
      { operators: 4, auc: 0.761 },
      { operators: 5, auc: 0.788 },
      { operators: 6, auc: 0.807 },
    ];
    return { points, note: "Empirical: the model is retrained for each cooperative size." };
  },

  async health(): Promise<Health> {
    await delay(200);
    const pop = await population();
    return {
      operators: OPERATORS.length,
      customers: pop.length,
      repayment_events: pop.length * 24,
      enrichment_signals: pop.length * 3,
      scored_customers: pop.length,
      active_consents: Math.round(pop.length * 0.98),
      cooperative_lifts: pop.length,
    };
  },

  async auditLog(params: { actor?: string; action?: string } = {}): Promise<AuditEntry[]> {
    await delay(220);
    const pop = await population();
    const rng = mulberry32(555);
    const actions = [
      "auth.login",
      "score.pooled",
      "score.solo",
      "score.cooperative",
      "ingest.events",
      "consent.grant",
      "operator.create",
    ];
    const actors = [...DEMO_ACCOUNTS.map((a) => a.email), "svc:sunlight-payg", "svc:azuri-metro"];
    const now = Date.now();
    const entries: AuditEntry[] = Array.from({ length: 24 }, (_, i) => {
      const action = actions[Math.floor(rng() * actions.length)];
      const c = pop[Math.floor(rng() * pop.length)];
      return {
        actor: actors[Math.floor(rng() * actors.length)],
        action,
        resource: action.startsWith("score") ? `customer:${c.identity_hash.slice(0, 12)}` : action.split(".")[0],
        metadata: {},
        created_at: new Date(now - i * 137_000 - Math.floor(rng() * 60_000)).toISOString(),
      };
    });
    return entries.filter(
      (e) =>
        (!params.actor || e.actor.toLowerCase().includes(params.actor.toLowerCase())) &&
        (!params.action || e.action.toLowerCase().includes(params.action.toLowerCase())),
    );
  },

  async activeModel(): Promise<ActiveModel> {
    await delay(180);
    return {
      version: "v3",
      threshold: THRESHOLD,
      metrics: { roc_auc: 0.807, pr_auc: 0.548, brier: 0.1123, ks: 0.492 },
      mlflow_run_id: "mock-run-9f3c1a2b",
      created_at: new Date(Date.now() - 6 * 86_400_000).toISOString(),
    };
  },

  async ingestEvents(events: IngestEvent[], _enrich = true): Promise<IngestResponse> {
    await delay(500);
    const errors: { index: number; message: string }[] = [];
    let inserted = 0;
    events.forEach((e, index) => {
      const ok = e && typeof e === "object" && "raw_identifier" in e && "due_date" in e && "status" in e;
      if (ok) inserted++;
      else errors.push({ index, message: "Missing raw_identifier, due_date, or status" });
    });
    // Pretend ~10% of otherwise-valid rows are already-seen duplicates.
    const duplicates = Math.floor(inserted * 0.1);
    inserted -= duplicates;
    return {
      report: {
        received: events.length,
        inserted,
        duplicates,
        failed: errors.length,
        customers_created: Math.min(inserted, new Set(events.map((e) => (e as Record<string, unknown>).raw_identifier)).size),
        errors,
      },
      customers_enriched: _enrich ? Math.ceil(inserted / 2) : 0,
      signals_written: _enrich ? inserted * 2 : 0,
    };
  },

  async createOperator(name: string, _country: string): Promise<{ id: string; name: string }> {
    await delay(260);
    return { id: uuidFrom(mulberry32(seedFromString(name + Date.now()))), name };
  },

  async issueApiKey(_operatorId: string): Promise<{ prefix: string; api_key: string }> {
    await delay(260);
    const rng = mulberry32(seedFromString(_operatorId + Date.now()));
    const prefix = `gsk_${hex(rng, 6)}`;
    return { prefix, api_key: `${prefix}_${hex(rng, 40)}` };
  },
};
