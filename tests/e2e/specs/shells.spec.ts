import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, SEED, signIn } from "./helpers";

// Task 4 acceptance: four themed shells, axe on every shell, screenshot baselines, phone viewports
// for Customer and Delivery, recovery route absent, placeholder wordmark labelled.

const SHELLS = [
  { portal: "customer", mobile: SEED.customer, heading: "Welcome, Demo Customer", role: "Customer" },
  { portal: "kitchen", mobile: SEED.kitchenManager, heading: "Overview", role: "Kitchen Manager" },
  { portal: "delivery", mobile: SEED.delivery, heading: "Home", role: "Delivery Agent" },
  { portal: "management", mobile: SEED.centralAdmin, heading: "Overview", role: "Central Administrator" },
] as const;

test("start page links to the four portals", async ({ page }) => {
  await page.goto("/");
  for (const name of ["Customer", "Kitchen", "Delivery", "Management"]) {
    await expect(page.getByRole("link", { name: new RegExp(name) })).toBeVisible();
  }
  await expectNoAxeViolations(page);
  await expect(page).toHaveScreenshot("landing.png", { fullPage: true });
});

for (const shell of SHELLS) {
  test.describe(`${shell.portal} portal`, () => {
    test("login page is accessible", async ({ page }) => {
      await page.goto(`/${shell.portal}/login`);
      await expect(page.getByRole("heading", { level: 1 })).toContainText("Sign in to");
      await expectNoAxeViolations(page);
      await expect(page).toHaveScreenshot(`${shell.portal}-login.png`, { fullPage: true });
    });

    test("signed-in shell is themed, labelled and accessible", async ({ page }) => {
      await signIn(page, shell.portal, shell.mobile);
      await expect(page.getByRole("heading", { level: 1, name: shell.heading })).toBeVisible();
      await expect(page.locator(`[data-portal="${shell.portal}"]`)).toBeVisible();
      await expect(page.getByText("Placeholder logo").first()).toBeVisible();
      await expect(page.getByTestId("account-roles")).toHaveText(shell.role);
      await expectNoAxeViolations(page);
      // The kitchen and management Overviews show live counts and the poll time, which change between runs.
      const live =
        shell.portal === "kitchen"
          ? [page.getByRole("list", { name: "Kitchen summary" }), page.getByTestId("poll-note"), page.getByTestId("intake")]
          : shell.portal === "management"
            ? [
                page.getByTestId("poll-note"),
                page.getByRole("region", { name: "Active orders by status" }),
                page.getByRole("region", { name: "Needs attention" }),
                page.getByRole("region", { name: "Kitchens" }),
              ]
            : [];
      // The CA's management Overview lists every kitchen, so its height depends on the database:
      // compare the viewport only there.
      await expect(page).toHaveScreenshot(`${shell.portal}-shell.png`, {
        fullPage: shell.portal !== "management",
        mask: live,
      });
    });
  });
}

test("unbuilt screens say so honestly", async ({ page }) => {
  // Task 10B built the Management sections of DDR-114 (2); Reports & Analytics is still Task 13.
  await signIn(page, "management", SEED.centralAdmin);
  await page.getByRole("link", { name: "Reports & Analytics" }).first().click();
  const section = page.locator("section", { has: page.getByRole("heading", { name: "Reports & Analytics" }) });
  await expect(section).toContainText("Not built yet");
  await expect(section).toContainText("Task 13");
  await expectNoAxeViolations(page);
});

test("visitors are sent to the portal login", async ({ page }) => {
  await page.goto("/management/reports");
  await expect(page).toHaveURL(/\/management\/login\?next=%2Fmanagement%2Freports$/);
});

test("kitchen staff cannot enter the management portal", async ({ page }) => {
  await signIn(page, "kitchen", SEED.kitchenStaff);
  await page.goto("/management");
  await expect(page.getByRole("alert")).toContainText("You don't have access to this area");
});

test("kitchen settings are shown to managers only", async ({ page }) => {
  await signIn(page, "kitchen", SEED.kitchenStaff);
  const nav = page.getByRole("navigation", { name: "Kitchen navigation" }).first();
  await expect(nav.getByRole("link", { name: "Recipes" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Settings" })).toHaveCount(0);
});

test("regional manager sees regional sections, not global ones", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  const nav = page.getByRole("navigation", { name: "Management navigation" }).first();
  await expect(nav.getByRole("link", { name: "Staff & Access" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Global Configuration" })).toHaveCount(0);
});

test("lost-mobile recovery route is absent (DDR-41)", async ({ page }) => {
  await page.goto("/customer/recover");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test("sign out ends the session", async ({ page }) => {
  await signIn(page, "delivery", SEED.delivery);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/delivery\/login(\?|$)/);
  await page.goto("/delivery");
  await expect(page).toHaveURL(/\/delivery\/login/);
});

test.describe("phone viewports @phone", () => {
  for (const shell of SHELLS.filter((s) => s.portal === "customer" || s.portal === "delivery")) {
    test(`${shell.portal} shell fits a phone and uses the bottom bar`, async ({ page }) => {
      await signIn(page, shell.portal, shell.mobile);
      await expect(page.getByRole("navigation", { name: /quick navigation/ })).toBeVisible();
      await expectNoHorizontalScroll(page);
      await expectNoAxeViolations(page);
      await expect(page).toHaveScreenshot(`${shell.portal}-phone.png`, { fullPage: true });

      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(page.locator("#portal-nav-drawer")).toBeVisible();
      await expectNoAxeViolations(page);
    });
  }
});
