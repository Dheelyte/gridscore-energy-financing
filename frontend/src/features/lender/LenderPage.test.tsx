import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api/client";

import { LenderPage } from "./LenderPage";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    api: {
      lenderPortfolio: vi.fn(),
      networkEffect: vi.fn(),
    },
  };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <LenderPage />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("LenderPage", () => {
  it("renders the network-effect chart and the debt-capacity KPI", async () => {
    vi.mocked(api.lenderPortfolio).mockResolvedValue({
      scored_customers: 120,
      average_default_probability: 0.15,
      approval_rate: 0.7,
      pd_histogram: [{ from: 0, to: 0.05, count: 10 }],
      tier_distribution: { A: 10, B: 0, C: 0, D: 0, E: 0 },
      operator_concentration: [{ operator: "Helios Energy", customers: 60, share: 0.5 }],
      newly_bankable_customers: 8,
      estimated_debt_capacity_unlocked_usd: 1600,
    });
    vi.mocked(api.networkEffect).mockResolvedValue({
      points: [
        { operators: 1, auc: 0.72, avg_history_months: 3, customers_covered: 100 },
        { operators: 5, auc: 0.78, avg_history_months: 12, customers_covered: 600 },
      ],
      note: "empirical",
    });

    renderPage();

    await waitFor(() => expect(screen.getByTestId("network-effect-chart")).toBeInTheDocument());
    expect(screen.getByText("$1,600")).toBeInTheDocument();
    expect(screen.getByText("Cooperative network effect")).toBeInTheDocument();
  });
});
