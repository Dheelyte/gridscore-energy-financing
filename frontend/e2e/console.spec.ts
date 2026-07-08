import { expect, test } from "@playwright/test";

// The app runs entirely on the built-in client-side mock (VITE_USE_MOCK !==
// "false"), so there is no backend to stub — we drive the real demo flow. The
// mock's first customer is the curated borderline case that flips reject →
// approve between the solo and pooled cooperative views.

test("quick-login → auto-selected borderline customer → watch the decision flip", async ({
  page,
}) => {
  await page.goto("/login");

  // One-click judge login as the operator analyst (lands on /console).
  await page.getByRole("button", { name: /enter as operator analyst/i }).click();

  // Dismiss the guided tour that auto-launches for first-time visitors.
  await page.getByRole("button", { name: /close tour/i }).click();

  // Landed on the console; the cooperative panel renders the solo view.
  await expect(page.getByText("Cooperative network effect")).toBeVisible();
  await expect(page.getByText("Solo view")).toBeVisible();

  // Reveal the pooled view and the reject → approve flip.
  await page.getByRole("button", { name: /pool the cooperative/i }).click();
  const flip = page.getByTestId("decision-flip");
  await expect(flip).toBeVisible();
  await expect(flip).toContainText(/approve/i);
});

test("lender analytics renders the network-effect chart and KPIs", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /enter as lender/i }).click();

  await expect(page.getByText("Scored customers")).toBeVisible();
  await expect(page.getByTestId("network-effect-chart")).toBeVisible();
  await expect(page.getByText("Debt capacity unlocked")).toBeVisible();
});
