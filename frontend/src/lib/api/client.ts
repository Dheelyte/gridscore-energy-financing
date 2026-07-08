/**
 * Typed API client built on the generated OpenAPI `schema.ts`.
 *
 * Types flow from the backend's OpenAPI document (run `npm run gen:api` after a
 * backend change), so request/response shapes cannot silently drift from the API.
 */
import { mockApi } from "./mock";
import type { paths } from "./schema";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Run entirely on client-side mock data (no backend). Default ON so the app is
 *  a self-contained demo; set `VITE_USE_MOCK=false` to talk to a real backend. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const TOKEN_KEY = "gridscore.token";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setAccessToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;

  if (!resp.ok) {
    const body = data as ApiErrorBody | null;
    throw new ApiError(
      resp.status,
      body?.error?.code ?? "error",
      body?.error?.message ?? resp.statusText,
      body?.error?.details,
    );
  }
  return data as T;
}

// ---- types from the OpenAPI schema ----
type J = "application/json";
export type Token = paths["/v1/auth/login"]["post"]["responses"]["200"]["content"][J];
export type Me = paths["/v1/auth/me"]["get"]["responses"]["200"]["content"][J];
export type Customer =
  paths["/v1/customers/{customer_id}"]["get"]["responses"]["200"]["content"][J];
export type ScoreOut = paths["/v1/score"]["post"]["responses"]["200"]["content"][J];
export type CooperativeOut =
  paths["/v1/score/cooperative"]["post"]["responses"]["200"]["content"][J];
export type IngestResponse = paths["/v1/ingest/events"]["post"]["responses"]["200"]["content"][J];
export type PortfolioSummary =
  paths["/v1/portfolio/summary"]["get"]["responses"]["200"]["content"][J];
export type PortfolioAnalytics =
  paths["/v1/analytics/portfolio"]["get"]["responses"]["200"]["content"][J];
export type NetworkEffect =
  paths["/v1/analytics/network-effect"]["get"]["responses"]["200"]["content"][J];
export type Health = paths["/v1/admin/health"]["get"]["responses"]["200"]["content"][J];
export type AuditEntry = paths["/v1/admin/audit"]["get"]["responses"]["200"]["content"][J][number];
export type ActiveModel = paths["/v1/admin/model"]["get"]["responses"]["200"]["content"][J];
export type ScoreView = "solo" | "pooled";
export type IngestEvent = Record<string, unknown>;

const realApi = {
  async login(email: string, password: string): Promise<Token> {
    const body = new URLSearchParams({ username: email, password });
    const token = await request<Token>("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    setAccessToken(token.access_token);
    return token;
  },

  me: () => request<Me>("/v1/auth/me"),

  listCustomers: () => request<Customer[]>("/v1/customers"),

  score: (customerId: string, view: ScoreView = "pooled") =>
    request<ScoreOut>("/v1/score", {
      method: "POST",
      body: JSON.stringify({ customer_id: customerId, view }),
    }),

  scoreCooperative: (customerId: string) =>
    request<CooperativeOut>("/v1/score/cooperative", {
      method: "POST",
      body: JSON.stringify({ customer_id: customerId }),
    }),

  ingestEvents: (events: IngestEvent[], enrich = true) =>
    request<IngestResponse>("/v1/ingest/events", {
      method: "POST",
      body: JSON.stringify({ events, enrich }),
    }),

  portfolio: () => request<PortfolioSummary>("/v1/portfolio/summary"),

  // ---- lender / admin analytics ----
  lenderPortfolio: () => request<PortfolioAnalytics>("/v1/analytics/portfolio"),
  networkEffect: () => request<NetworkEffect>("/v1/analytics/network-effect"),
  health: () => request<Health>("/v1/admin/health"),
  auditLog: (params: { actor?: string; action?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.actor) q.set("actor", params.actor);
    if (params.action) q.set("action", params.action);
    const qs = q.toString();
    return request<AuditEntry[]>(`/v1/admin/audit${qs ? `?${qs}` : ""}`);
  },
  activeModel: () => request<ActiveModel>("/v1/admin/model"),

  // ---- operator onboarding (platform admin) ----
  createOperator: (name: string, country: string) =>
    request<{ id: string; name: string }>("/v1/operators", {
      method: "POST",
      body: JSON.stringify({ name, country }),
    }),
  issueApiKey: (operatorId: string) =>
    request<{ prefix: string; api_key: string }>(`/v1/operators/${operatorId}/api-keys`, {
      method: "POST",
    }),
};

// When VITE_USE_MOCK is not "false", every call is served by the self-contained
// client-side mock (no backend). The mock implements the same surface as realApi.
export const api: typeof realApi = USE_MOCK ? (mockApi as typeof realApi) : realApi;
