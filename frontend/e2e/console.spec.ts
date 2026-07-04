import { expect, test, type Page } from "@playwright/test";

// An identity hash for the single mocked customer (auto-selected by the console).
const DEMO_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

const score = (over: Record<string, unknown>) => ({
  customer_id: "demo",
  view: "pooled",
  default_probability: 0.1,
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
  ],
  ...over,
});

async function mockApi(page: Page) {
  await page.route("**/v1/auth/login", (r) =>
    r.fulfill({ json: { access_token: "t", refresh_token: "r", token_type: "bearer" } }),
  );
  await page.route("**/v1/auth/me", (r) =>
    r.fulfill({
      json: {
        kind: "user",
        subject_id: "u1",
        role: "operator_admin",
        operator_id: "op",
        email: "ops@a.example",
      },
    }),
  );
  await page.route("**/v1/customers", (r) =>
    r.fulfill({
      json: [
        {
          id: "demo",
          identity_hash: DEMO_HASH,
          home_operator_id: "op",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    }),
  );
  await page.route("**/v1/score", (r) => r.fulfill({ json: score({}) }));
  await page.route("**/v1/score/cooperative", (r) =>
    r.fulfill({
      json: {
        customer_id: "demo",
        solo: score({
          view: "solo",
          default_probability: 0.36,
          energy_credit_score: 536,
          risk_tier: "E",
          approved: false,
        }),
        pooled: score({}),
        pd_delta: 0.26,
        confidence_delta: 0.3,
        score_delta: 119,
        decision_flips: true,
        lift_metric: 0.26,
      },
    }),
  );
}

test("login → look up the borderline customer → watch the decision flip", async ({ page }) => {
  await mockApi(page);

  await page.goto("/login");
  await page.getByPlaceholder("Email").fill("ops@a.example");
  await page.getByPlaceholder("Password").fill("demo-password-123");
  await page.getByRole("button", { name: /sign in/i }).click();

  // Landed on the console; the cooperative panel renders the solo view.
  await expect(page.getByText("Cooperative network effect")).toBeVisible();
  await expect(page.getByText("Solo view")).toBeVisible();

  // Reveal the pooled view and the reject → approve flip.
  await page.getByRole("button", { name: /pool the cooperative/i }).click();
  const flip = page.getByTestId("decision-flip");
  await expect(flip).toBeVisible();
  await expect(flip).toContainText(/approve/i);
});
