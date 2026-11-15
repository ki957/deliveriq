import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, SEED, signIn } from "./helpers";

test("CA sees persisted P3 demo, labelled GPS and matching Simulated reports", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await page.goto("/management/data-pipelines/p3_synthetic");
  await expect(page.getByRole("heading", { name: "Simulated data" })).toBeVisible();
  await expect(page.getByText(/Demo: .* · ready/)).toBeVisible();
  await expect(page.getByLabel("Input").locator("option")).toHaveCount(1);
  await expect(page.getByLabel("Input")).toContainText("7-day demo");
  await page.getByLabel("Simulated GPS track").selectOption({ index: 1 });
  await expect(page.getByText("Simulated data · complete GPS track, 61 points")).toBeVisible();
  await expectNoAxeViolations(page);
  await page.getByRole("link", { name: "View Simulated reports" }).click();
  await page.getByRole("button", { name: "Simulated" }).click();
  await page.getByRole("button", { name: "Use demo dates" }).click();
  await expect(page.getByTestId("simulated-note")).toContainText("Simulated data");
  await expect(page.getByTestId("kpi-orders_placed")).toContainText("70");
  await expectNoAxeViolations(page);
});

test("RM views P3 only for their region and cannot run it", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  await page.goto("/management/data-pipelines/p3_synthetic");
  await expect(page.getByRole("heading", { name: "Simulated data" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run pipeline" })).toHaveCount(0);
  await expect(page.getByLabel("Simulated GPS track")).toBeVisible();
  await expectNoAxeViolations(page);
});
