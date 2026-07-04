import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CooperativeOut, ScoreOut } from "@/lib/api/client";

import { CooperativePanel } from "./CooperativePanel";

function score(over: Partial<ScoreOut>): ScoreOut {
  return {
    customer_id: "c1",
    view: "pooled",
    default_probability: 0.1,
    energy_credit_score: 655,
    risk_tier: "B",
    approved: true,
    model_version: "1",
    top_factors: [],
    ...over,
  };
}

const data: CooperativeOut = {
  customer_id: "c1",
  solo: score({
    view: "solo",
    default_probability: 0.36,
    energy_credit_score: 536,
    risk_tier: "E",
    approved: false,
  }),
  pooled: score({
    default_probability: 0.1,
    energy_credit_score: 655,
    risk_tier: "B",
    approved: true,
  }),
  pd_delta: 0.26,
  confidence_delta: 0.3,
  score_delta: 119,
  decision_flips: true,
  lift_metric: 0.26,
};

describe("CooperativePanel", () => {
  it("hides the pooled reveal until the cooperative is pooled", () => {
    render(<CooperativePanel data={data} />);
    expect(screen.getByText("Solo view")).toBeInTheDocument();
    expect(screen.queryByTestId("lift-summary")).not.toBeInTheDocument();
    expect(screen.queryByTestId("decision-flip")).not.toBeInTheDocument();
  });

  it("reveals the pooled view, the lift, and the reject→approve flip", () => {
    render(<CooperativePanel data={data} />);
    fireEvent.click(screen.getByRole("button", { name: /pool the cooperative/i }));

    expect(screen.getByTestId("lift-summary")).toBeInTheDocument();
    const flip = screen.getByTestId("decision-flip");
    expect(flip).toHaveTextContent(/reject/i);
    expect(flip).toHaveTextContent(/approve/i);
    expect(screen.getByText("+119")).toBeInTheDocument();
  });
});
