import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/app/App";

describe("App landing page", () => {
  beforeEach(() => {
    // Resolve health as online so the badge reaches a stable state.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true } as Response)),
    );
  });

  it("renders the product headline", () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Africa's energy lenders/i);
  });

  it("labels the data as synthetic (honesty is a feature)", () => {
    render(<App />);
    expect(screen.getByText(/Synthetic data only/i)).toBeInTheDocument();
  });

  it("surfaces the cooperative network effect", () => {
    render(<App />);
    expect(screen.getByText(/Cooperative network effect/i)).toBeInTheDocument();
  });
});
