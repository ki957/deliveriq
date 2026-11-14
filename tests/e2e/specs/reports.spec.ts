import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, SEED, signIn } from "./helpers";

// Task 13 acceptance (DDR-117): every KPI shows its definition status, freshness is visible, scope is enforced
// (RM own regions, CA all) across the page and the CSV export, and real data never includes TEST rows.

test("a Central Administrator reads labelled KPIs, freshness and an audited export", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  await page.getByRole("link", { name: "Reports & Analytics" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Reports & Analytics" })).toBeVisible();
  await expect(page.getByTestId("definition-note")).toContainText("pending approval (DDR-44)");
  await expect(page.getByTestId("freshness")).toContainText(/Data as of|Never built/);
  const cards = page.getByRole("list", { name: "Key figures" });
  await expect(cards.getByRole("listitem")).toHaveCount(13);
  await expect(cards.getByText("Definition pending approval (DDR-44)")).toHaveCount(13);
  await expect(page.getByTestId("real-note")).toContainText("Every order in this POC is a TEST order");
  await expect(page.getByRole("list", { name: "Not available" })).toContainText("Promotions");
  await expectNoAxeViolations(page);

  const csv = await page.request.get("/api/v1/management/reports.csv?dataset=analytics");
  expect(csv.status()).toBe(200);
  expect(await csv.text()).toContain("Definition pending approval (DDR-44)");

  await page.getByRole("button", { name: "Simulated" }).click();
  await expect(page.getByTestId("dataset-not-built")).toContainText("Not built yet (Task 14)");
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveCount(0);
  await expectNoAxeViolations(page);
});

test("a Regional Manager sees only own-region kitchens and no pipeline control", async ({ browser }, info) => {
  const context = await browser.newContext({ viewport: info.project.use.viewport ?? null });
  const rm = await context.newPage();
  await signIn(rm, "management", SEED.regionalManager);
  await rm.goto("/management/reports");
  const kitchens = rm.getByLabel("Kitchen");
  await expect(kitchens.locator("option")).not.toContainText(["TEST – E2E Kitchen"]);
  await expect(rm.getByRole("link", { name: "Run P2" })).toHaveCount(0);
  // The other region's TEST kitchen reads as not found for this RM, on the page and the export.
  const other = await browser.newContext();
  const otherRm = await other.newPage();
  await signIn(otherRm, "management", SEED.otherRegionalManager);
  const body = (await (await otherRm.request.get("/api/v1/management/reports")).json()) as {
    kitchens: { id: string; name: string }[];
  };
  const foreign = body.kitchens.find((k) => k.name === "TEST – E2E Kitchen");
  expect(foreign).toBeDefined();
  expect((await rm.request.get(`/api/v1/management/reports?kitchen_id=${foreign?.id}`)).status()).toBe(404);
  expect((await rm.request.get(`/api/v1/management/reports.csv?kitchen_id=${foreign?.id}`)).status()).toBe(404);
  await expectNoAxeViolations(rm);
  await context.close();
  await other.close();
});
