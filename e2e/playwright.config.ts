import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// Repo root, so both servers spawn with the workspace as their cwd.
// Playwright loads this config as CommonJS, so __dirname is available.
const root = path.resolve(__dirname, "..");

// Dedicated E2E ports so we never collide with (or reuse) a dev server the
// developer already has running on the default 3000/8000.
const WEB_PORT = 3100;
const API_PORT = 8001;
export const API_URL = `http://localhost:${API_PORT}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Run serially: the canvas tests each boot a full React Flow app from a single
  // `next start` server (and a single API), so concurrent workers contend on hydration +
  // the codegen proxy and flake. The build dominates runtime, so serial costs little.
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Production build, not `next dev`: fully compiled, no HMR/Fast-Refresh remounts —
      // the canvas state stays put through the test (deterministic E2E).
      command:
        `pnpm --filter @calypr/web exec next build && ` +
        `pnpm --filter @calypr/web exec next start --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      cwd: root,
      env: { CALYPR_API_URL: API_URL },
      reuseExistingServer: false,
      timeout: 180_000,
    },
    {
      command: `uv run uvicorn calypr_api.main:app --port ${API_PORT}`,
      url: `${API_URL}/health`,
      cwd: root,
      // Pin the AI assistant to the keyless deterministic "fake" path so the suite never
      // depends on a provider key (a developer's .env may set CALYPR_ASSISTANT_MODEL to a
      // real model). load_dotenv(override=False) won't clobber this.
      // ADMIN_TOKEN lets the round-trip spec promote a workspace into the beta tier through the
      // real operator endpoint (and demote it again), so entitlement gating is exercised
      // end-to-end rather than stubbed.
      // STRIPE_* are pinned empty for the same reason CALYPR_ASSISTANT_MODEL is pinned to
      // "fake": the API loads the repo-root .env, so a developer with real keys there would
      // otherwise get a different suite than CI — billing would report `enabled` and the
      // checkout specs would fail locally while passing in CI (or worse, the reverse).
      env: {
        CALYPR_ASSISTANT_MODEL: "fake",
        CALYPR_ADMIN_TOKEN: "e2e-admin-token",
        STRIPE_SECRET_KEY: "",
        STRIPE_WEBHOOK_SECRET: "",
        STRIPE_PLUS_PRICE_ID: "",
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
