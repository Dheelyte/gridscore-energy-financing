import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e. The spec mocks the API via request interception so it runs
 * hermetically in CI (no live backend / DB needed). The same UI flow works
 * against a real seeded backend by pointing VITE_API_BASE_URL at it and removing
 * the route mocks.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://localhost:4173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
