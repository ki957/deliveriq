import { defineConfig, devices } from "@playwright/test";

// Runs inside the pinned Playwright container (`make e2e`), so screenshots are reproducible
// locally and in CI. Chromium only, headless, 2 workers (DDR-62).
const snapshotDir = process.env.E2E_SNAPSHOT_DIR ?? "./__screenshots__";

export default defineConfig({
  testDir: "./specs",
  outputDir: process.env.E2E_OUTPUT_DIR ?? "./test-results",
  snapshotPathTemplate: `${snapshotDir}/{projectName}/{testFilePath}/{arg}{ext}`,
  fullyParallel: false,
  workers: 2,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  reporter: [["list"]],
  expect: {
    toHaveScreenshot: { animations: "disabled", caret: "hide", maxDiffPixelRatio: 0.01 },
  },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    colorScheme: "light",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } }, grepInvert: /@phone|@kitchen/ },
    // `@devices` tests run on every project: desktop, both phones and the tablet (Task 6 acceptance).
    { name: "phone-360", use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true }, grep: /@phone|@devices/ },
    { name: "phone-390", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }, grep: /@phone|@devices/ },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 }, hasTouch: true }, grep: /@tablet|@devices|@kitchen/ },
    // Kitchen display system (KI-U1, DDR-21, DDR-112 (8)): the primary kitchen device.
    { name: "kds", use: { ...devices["Desktop Chrome"], viewport: { width: 1920, height: 1080 } }, grep: /@kitchen/ },
  ],
});
