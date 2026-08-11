import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: "http://127.0.0.1:43123", launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : undefined },
  webServer: { command: "python -m uvicorn novel_translator.web.app:create_app --factory --host 127.0.0.1 --port 43123", port: 43123, reuseExistingServer: true }
});
