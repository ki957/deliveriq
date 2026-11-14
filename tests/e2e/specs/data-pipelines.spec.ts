import { expect, test, type Page } from "@playwright/test";

import { expectNoAxeViolations, SEED, signIn } from "./helpers";

// Task 5 UI criteria (DATA_PIPELINE_DESIGN §13): the CA runs P1 from the UI and sees the persisted
// counts; a TEST fault run shows quarantined records with reasons; the RM views own-region runs with
// no action controls. Needs the worker (`make worker`). Runs in this file are serial: one active run
// per pipeline (DDR-67).
test.describe.configure({ mode: "serial" });

const RUN_DONE = 90_000;

async function openP1(page: Page): Promise<void> {
  await page.getByRole("link", { name: "Data & Pipelines" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Data & Pipelines" })).toBeVisible();
  await page.getByRole("link", { name: "P1 SOP master-data ETL" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "P1 SOP master-data ETL" })).toBeVisible();
}

async function runP1(page: Page, input: string): Promise<void> {
  await page.getByLabel("Input").selectOption(input);
  await page.getByRole("button", { name: "Run pipeline" }).click();
  await expect(page).toHaveURL(/\/management\/data-pipelines\/runs\/[0-9a-f-]{36}$/);
}

test("Central Administrator runs the SOP import from the UI and sees the persisted counts", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await openP1(page);
  await expectNoAxeViolations(page);
  // The Run panel only: run history depends on how many runs the database holds.
  await expect(page.getByTestId("run-controls")).toHaveScreenshot("pipeline-p1.png");

  await runP1(page, "sop");
  await expect(page.getByTestId("run-status")).toHaveText("Succeeded", { timeout: RUN_DONE });
  await expect(page.getByTestId("count-cards")).toHaveText("104");
  await expect(page.getByTestId("count-ingredient_lines")).toHaveText("616");
  await expect(page.getByTestId("count-duplicate_candidates")).toHaveText("2");
  await expect(page.getByRole("region", { name: "Stages" })).toContainText("9. report");
  await expect(page.getByRole("link", { name: "Download report" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry run" })).toHaveCount(0); // succeeded
  await expectNoAxeViolations(page);
});

test("a TEST fault run is labelled and shows quarantined records with reasons", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await openP1(page);
  await runP1(page, "fault:records");
  await expect(page.getByTestId("run-status")).toHaveText("Completed with quarantine", { timeout: RUN_DONE });
  await expect(page.getByTestId("test-badge").first()).toHaveText("Test run");
  const errors = page.getByRole("region", { name: "Quarantined records and errors" });
  for (const reason of ["MISSING_UNIT", "ZERO_QUANTITY", "UNKNOWN_UNIT", "MISSING_FIELD", "DUPLICATE_CARD_ID"]) {
    await expect(errors).toContainText(reason);
  }
  await expectNoAxeViolations(page);
  await expect(page).toHaveScreenshot("run-fault.png", {
    fullPage: true,
    mask: [page.locator("dl").first(), page.getByRole("heading", { level: 1 }), page.getByRole("region", { name: "Stages" })],
  });
});

test("Regional Manager views runs without any action control", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  await openP1(page);
  await expect(page.getByRole("button", { name: "Run pipeline" })).toHaveCount(0);
  await page.getByRole("link", { name: "View run" }).first().click();
  await expect(page.getByRole("region", { name: "Stages" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Retry run|Cancel run/ })).toHaveCount(0);
  await expectNoAxeViolations(page);
});

test("unbuilt pipelines are labelled with their task", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  await page.getByRole("link", { name: "Data & Pipelines" }).first().click();
  await expect(page.getByRole("region", { name: "Data" })).toContainText("Not built yet (Task 12)");
  await expect(page.getByRole("region", { name: "Knowledge" })).toContainText("Not built yet (Task 15)");
  // P2 landing covers every region: no backlog for an RM (DDR-116 (10)).
  await expect(page.getByRole("heading", { name: "P2 event landing (outbox → raw)" })).toHaveCount(0);
  await expect(page).toHaveScreenshot("pipelines-overview.png", {
    fullPage: true,
    mask: [page.getByRole("region", { name: "Data" }).locator("li").first()],
  });
});

test("Central Administrator sees the live P2 outbox backlog (DDR-116 (10), (12))", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await page.getByRole("link", { name: "Data & Pipelines" }).first().click();
  const panel = page.getByRole("region", { name: "P2 event landing (outbox → raw)" });
  const figures = panel.getByTestId("backlog");
  await expect(figures).toContainText("Waiting");
  await expect(figures).toContainText("Oldest waiting");
  // Events have landed (every order action emits one); the count is persisted, never invented.
  await expect(figures.getByText("Landed").locator("..")).not.toContainText(/Landed0$/);
  await expect(panel).toContainText("Warning after 5 min (test default, not a final value)");
  await expectNoAxeViolations(page);
});
