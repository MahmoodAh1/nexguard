import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end config. Assumes the backend (seeded) is on :8000 and the frontend
 * on :3000 — the CI e2e job boots both, or run them locally first.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
