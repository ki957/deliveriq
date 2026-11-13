import { expect, test, type Browser, type Page } from "@playwright/test";

import { expectNoAxeViolations, SEED, signIn } from "./helpers";

// Task 5 recipe approval and menu publication through the UI (DDR-10, DDR-31, DDR-50, DDR-54).
// `make e2e` first adds a fresh `TEST – E2E <n>` DRAFT recipe and menu item (DDR-108), so the full
// path KM → CA → KM → RM can run on every invocation. Dish D stays untouched for the live demo.
test.describe.configure({ mode: "serial" });

async function as(browser: Browser, portal: string, mobile: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signIn(page, portal, mobile);
  return page;
}

async function openE2eRecipe(page: Page, status: string): Promise<string> {
  await page.getByRole("link", { name: "Recipes" }).first().click();
  await page.getByLabel("Search by name or card ID").fill("TEST – E2E");
  await page.getByLabel("Status").selectOption(status);
  const link = page.getByRole("table").getByRole("link").first();
  const name = (await link.textContent()) ?? "";
  expect(name).toMatch(/^TEST – E2E \d+$/);
  await link.click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  return name;
}

async function act(page: Page, button: string, confirm: string): Promise<void> {
  await page.getByRole("button", { name: button }).click();
  await page.getByLabel(`Reason for "${button}"`).fill("E2E workflow check");
  await page.getByRole("button", { name: confirm }).click();
  await expect(page.getByText(`${button}: done.`)).toBeVisible();
}

test("Kitchen Staff can read recipes and the review queue but has no workflow controls", async ({ page }) => {
  await signIn(page, "kitchen", SEED.kitchenStaff);
  await page.getByRole("link", { name: "Recipes" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Recipes" })).toBeVisible();
  await expectNoAxeViolations(page);
  // Viewport only: `make e2e` imports the 104 SOP recipes first, so the list always fills the
  // viewport; E2E recipes accumulate below it.
  const main = page.locator("main");
  await expect(page).toHaveScreenshot("recipes-list.png", {
    mask: [main.getByRole("table"), main.getByRole("status")],
  });

  await page.getByLabel("Search by name or card ID").fill("MENU008");
  await page.getByRole("table").getByRole("link").first().click();
  await expect(page.getByText(/DUPLICATE_BOM/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Source lineage" })).toContainText("SHA-256");
  await expect(page.getByRole("region", { name: "Workflow" })).toHaveCount(0);
  await expectNoAxeViolations(page);

  await page.getByRole("link", { name: "Review Queue" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Review queue" })).toBeVisible();
  await expect(page.getByText("Missing batch recipe").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Acknowledge" })).toHaveCount(0);
  await expectNoAxeViolations(page);
});

test("a TEST recipe goes from draft to published: KM, CA product owner, KM activates, RM publishes", async ({
  browser,
}) => {
  const km = await as(browser, "kitchen", SEED.kitchenManager);
  const name = await openE2eRecipe(km, "DRAFT");
  await expect(km.getByTestId("test-badge").first()).toBeVisible();
  await act(km, "Submit for validation", "Confirm submit");
  await act(km, "Mark validated", "Confirm validate");
  await expectNoAxeViolations(km);
  const signoffs = km.getByRole("region", { name: "Release sign-offs" });
  const record = signoffs.getByRole("button", { name: "Record sign-off" });
  for (const [i, role] of ["Chef", "Food-safety lead", "Inventory owner", "Kitchen Manager"].entries()) {
    await record.first().click();
    await km.getByLabel(`Note for the ${role} sign-off`).fill("E2E check");
    await signoffs.getByRole("button", { name: "Confirm sign-off" }).click();
    await expect(record).toHaveCount(3 - i);
  }
  // Five sign-offs are required: activation is refused while the product owner's is missing.
  await km.getByRole("button", { name: "Activate" }).click();
  await expect(km.getByText(/Missing sign-offs: Product owner/)).toBeVisible();
  await km.getByRole("button", { name: "Cancel" }).click();

  const ca = await as(browser, "management", SEED.centralAdmin);
  await ca.getByRole("link", { name: "Recipe Sign-off" }).first().click();
  await ca.getByRole("link", { name, exact: true }).click();
  await ca.getByRole("button", { name: "Record product-owner sign-off" }).click();
  await ca.getByLabel("Note for the product-owner sign-off").fill("E2E approval");
  await ca.getByRole("button", { name: "Confirm sign-off" }).click();
  await expect(ca.getByText("Sign-off recorded.")).toBeVisible();
  await expectNoAxeViolations(ca);

  await km.reload();
  await act(km, "Activate", "Confirm activate");
  await expect(km.getByText("Active", { exact: true })).toBeVisible();

  const rm = await as(browser, "management", SEED.regionalManager);
  await rm.getByRole("link", { name: "Menu Publication" }).first().click();
  const row = rm.getByRole("listitem").filter({ has: rm.getByTestId("menu-item-name").getByText(name, { exact: true }) });
  await row.getByRole("button", { name: "Mark ready for publication" }).click();
  await expect(row.getByText("Ready for publication", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: "Publish" }).click();
  await expect(row.getByText("Published", { exact: true })).toBeVisible();
  await expectNoAxeViolations(rm);
  // The published row only (badge, status, price, recipe state): the list length grows with every run.
  await expect(row).toHaveScreenshot("menu-publication.png", { mask: [row.getByTestId("menu-item-name")] });

  const menu = await rm.request.get("/api/v1/menu/items");
  const published = ((await menu.json()) as { name: string; is_test_fixture: boolean }[]).find((i) => i.name === name);
  expect(published?.is_test_fixture).toBe(true);
});

test("Kitchen Staff and Kitchen Manager have no Management publication access", async ({ page }) => {
  await signIn(page, "kitchen", SEED.kitchenManager);
  await page.goto("/management/menu-publication");
  await expect(page.getByRole("alert")).toContainText("You don't have access to this area");
});
