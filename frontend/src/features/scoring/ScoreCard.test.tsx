import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ScoreOut } from "@/lib/api/client";

import { ScoreCard } from "./ScoreCard";

const score: ScoreOut = {
  customer_id: "c1",
  view: "pooled",
  default_probability: 0.098,
  energy_credit_score: 655,
  risk_tier: "B",
  approved: true,
  model_version: "1",
  top_factors: [
    {
      feature: "payg_repayment_rate",
      label: "PAYG on-time repayment rate",
      value: 0.93,
      contribution: -0.6,
      direction: "decreases",
    },
    {
      feature: "prior_defaults",
      label: "Prior defaults on record",
      value: 0,
      contribution: 0.4,
      direction: "increases",
    },
  ],
};

describe("ScoreCard", () => {
  it("shows the score, decision, PD and SHAP factors", () => {
    render(<ScoreCard score={score} />);
    expect(screen.getByText("655")).toBeInTheDocument();
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText(/9\.8%/)).toBeInTheDocument();
    expect(screen.getByText("PAYG on-time repayment rate")).toBeInTheDocument();
    expect(screen.getByText("Prior defaults on record")).toBeInTheDocument();
  });
});
