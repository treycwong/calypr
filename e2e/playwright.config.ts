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
  reporter: "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `pnpm --filter @calypr/web exec next dev --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      cwd: root,
      env: { CALYPR_API_URL: API_URL },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `uv run uvicorn calypr_api.main:app --port ${API_PORT}`,
      url: `${API_URL}/health`,
      cwd: root,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
