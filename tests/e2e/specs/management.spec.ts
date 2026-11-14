import { expect, test, type Browser, type Page, type TestInfo } from "@playwright/test";

import {
  expectNoAxeViolations,
  expectNoHorizontalScroll,
  newTestMobile,
  registerCustomer,
  SEED,
  signIn,
} from "./helpers";

// Task 10 acceptance (DDR-114): the unified management portal. Desktop-first; navigation also on tablet
// and phone-390 (`@devices`, phone-360 skipped). Region scope uses the second-region RM fixture
// (fixtures load-e2e-region, REG-ETE-001). Every TEST order this spec accepts is ended ("Cannot fulfil"),
// and every staff role it adds is removed again.

const CSRF = { "X-DeliverIQ-CSRF": "1" };
const CHENNAI = { lat: 13.0835, lng: 80.271 }; // fixture seed address (fixtures.py)

async function as(browser: Browser, info: TestInfo, portal: string, mobile: string): Promise<Page> {
  const context = await browser.newContext({ viewport: info.project.use.viewport ?? null });
  const page = await context.newPage();
  await signIn(page, portal, mobile);
  return page;
}

/** A fresh TEST customer places a COD order for 5 × Dish A, and the Kitchen Manager accepts it. */
async function acceptedTestOrder(browser: Browser, info: TestInfo): Promise<string> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/customer/login");
  await registerCustomer(page, newTestMobile(), "TEST E2E Customer");
  await expect(page).toHaveURL(/\/customer$/);
  const address = await page.request.post("/api/v1/me/addresses", {
    headers: CSRF,
    data: { label: "TEST – Home", address_line: "TEST – 1 Fixture Street", ...CHENNAI, make_default: true },
  });
  expect(address.status()).toBe(201);
  const menu = await page.request.get(`/api/v1/menu/items?q=${encodeURIComponent("Synthetic Dish A")}`);
  const dish = ((await menu.json()) as { id: string; name: string; price_paise: number }[]).find(
    (d) => d.name === "TEST – Synthetic Dish A",
  );
  expect(dish).toBeDefined();
  const order = await page.request.post("/api/v1/orders", {
    headers: { ...CSRF, "Idempotency-Key": crypto.randomUUID() },
    data: {
      lines: [{ menu_item_id: dish?.id, quantity: 5, unit_price_paise: dish?.price_paise }],
      payment_method: "COD",
      address_id: ((await address.json()) as { id: string }).id,
    },
  });
  expect(order.status()).toBe(201);
  const id = ((await order.json()) as { id: string }).id;
  await context.close();

  const km = await as(browser, info, "kitchen", SEED.kitchenManager);
  const accept = await km.request.post(`/api/v1/kitchen/orders/${id}/accept`, { headers: CSRF });
  expect(accept.status()).toBe(200);
  await km.context().close();
  return id;
}

async function openSection(page: Page, name: string): Promise<void> {
  // The sidebar shows from the `lg` breakpoint (1024 px); narrower screens use the drawer.
  if ((page.viewportSize()?.width ?? 0) < 1024) await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name, exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
}

test("a Regional Manager opens every built section; each is labelled and accessible", async ({ page }) => {
  await signIn(page, "management", SEED.regionalManager);
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  await expect(page.getByTestId("kpi-note")).toContainText("Task 13");
  await expectNoAxeViolations(page);
  await expect(page).toHaveScreenshot("overview.png", {
    fullPage: true,
    mask: [
      page.getByTestId("poll-note"),
      page.getByRole("region", { name: "Active orders by status" }),
      page.getByRole("region", { name: "Needs attention" }),
      page.getByRole("region", { name: "Kitchens" }),
    ],
  });

  for (const name of [
    "Kitchen Operations",
    "Delivery Operations",
    "Orders & Exceptions",
    "Menu & Inventory",
    "Payments & Promotions",
    "Staff & Access",
    "Regional Audit Logs",
  ]) {
    await openSection(page, name);
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expectNoAxeViolations(page);
  }

  // Kitchen settings come from the existing kitchen API; the test defaults stay labelled.
  await openSection(page, "Kitchen Operations");
  await expect(page.getByRole("heading", { level: 2, name: /^Settings · / })).toBeVisible();
  await expect(page.getByText("Test default, not a final value (DDR-42 open)").first()).toBeVisible();

  await openSection(page, "Menu & Inventory");
  await expect(page.getByRole("table", { name: "Stock", exact: true })).toBeVisible();
  await expect(page.getByTestId("test-badge").first()).toContainText("Test stock");

  await openSection(page, "Payments & Promotions");
  await expect(page.getByTestId("refund-rules")).toContainText("Disabled: no threshold configured (DDR-44)");

  // RM-only nav: no global sections (MG-10).
  for (const hidden of ["Global Audit Logs", "Global Configuration", "Global Staff & Regional Manager Access"]) {
    await expect(page.getByRole("link", { name: hidden })).toHaveCount(0);
  }
});

test("unbuilt management sections say why", async ({ page }) => {
  await signIn(page, "management", SEED.centralAdmin);
  for (const [name, reason] of [
    ["Customers & Support", "no support ticket or review model"],
    ["Global Configuration", "#10 §17"],
    ["Integrations & Providers", "Task 15"],
    ["YAML Configuration Management", "DDR-44, class B"],
  ] as const) {
    await openSection(page, name);
    const section = page.locator("section", { has: page.getByRole("heading", { name }) });
    await expect(section).toContainText("Not built yet");
    await expect(section).toContainText(reason);
  }
  await expectNoAxeViolations(page);
  await expect(page).toHaveScreenshot("yaml-placeholder.png", { fullPage: true });
});

test("a Regional Manager of another region sees nothing of Chennai", async ({ browser }, info) => {
  const orderId = await acceptedTestOrder(browser, info);
  const rm = await as(browser, info, "management", SEED.regionalManager);
  const other = await as(browser, info, "management", SEED.otherRegionalManager);

  // UI: the Chennai RM finds the order; the other RM gets "not found" on the same URL.
  await rm.goto(`/management/orders/${orderId}`);
  await expect(rm.getByRole("heading", { level: 1, name: `Order ${orderId.slice(0, 8)}` })).toBeVisible();
  await other.goto(`/management/orders/${orderId}`);
  await expect(other.getByText("Order not found in your scope")).toBeVisible();

  // Kitchens: only the second region's TEST kitchen.
  await other.goto("/management/kitchen");
  await expect(other.getByRole("table", { name: "Kitchens" })).toContainText("TEST – E2E Kitchen");
  await expect(other.getByRole("table", { name: "Kitchens" })).not.toContainText("KIT-CHN-001");
  await expectNoAxeViolations(other);

  // API and CSV export use the same scope (DDR-114 (8)).
  const mine = await rm.request.get("/api/v1/management/orders.csv");
  expect(mine.status()).toBe(200);
  expect(await mine.text()).toContain(orderId);
  const theirs = await other.request.get("/api/v1/management/orders.csv");
  expect(theirs.status()).toBe(200);
  expect(await theirs.text()).not.toContain(orderId);
  const kitchens = (await (await rm.request.get("/api/v1/management/kitchens")).json()) as { id: string }[];
  for (const k of kitchens) {
    expect((await other.request.get(`/api/v1/management/kitchens/${k.id}/inventory`)).status()).toBe(404);
  }

  // Clean up: end the order so no capacity or stock stays held.
  const end = await rm.request.post(`/api/v1/kitchen/orders/${orderId}/reject`, {
    headers: CSRF,
    data: { reason: "E2E test cleanup" },
  });
  expect(end.status()).toBe(200);
});

test("an order the kitchen cannot fulfil is ended with a reason, shown in its timeline and audited", async ({
  browser,
}, info) => {
  const orderId = await acceptedTestOrder(browser, info);
  const rm = await as(browser, info, "management", SEED.regionalManager);
  await rm.goto("/management/orders");
  await rm.getByLabel("Status").selectOption("ACCEPTED");
  await rm.getByRole("button", { name: "Apply filters" }).click();
  await rm.getByRole("link", { name: orderId.slice(0, 8) }).click();
  await expect(rm.getByRole("heading", { level: 1, name: `Order ${orderId.slice(0, 8)}` })).toBeVisible();
  await expect(rm.getByText("Test order").first()).toBeVisible();
  await expectNoAxeViolations(rm);

  await rm.getByRole("button", { name: "Cannot fulfil" }).click();
  await rm.getByLabel("Why can the kitchen not fulfil this order?").fill("E2E: ingredient spoiled");
  await rm.getByRole("button", { name: "Reject order" }).click();
  await expect(rm.getByRole("table", { name: "Timeline" })).toContainText("E2E: ingredient spoiled");
  await expect(rm.getByRole("button", { name: "Cannot fulfil" })).toHaveCount(0);

  // The export of the current view is itself audited (DDR-114 (8)). Export events carry no region, so
  // they appear in the CA's Global Audit Logs (DDR-114 (7)).
  const csv = await rm.request.get("/api/v1/management/orders.csv?status=REJECTED");
  expect(csv.status()).toBe(200);
  await rm.goto("/management/regional-audit");
  await expect(rm.getByRole("heading", { level: 1, name: "Regional Audit Logs" })).toBeVisible();
  await expectNoAxeViolations(rm);

  const ca = await as(browser, info, "management", SEED.centralAdmin);
  await ca.goto("/management/global-audit");
  await ca.getByLabel("Action", { exact: true }).fill("management.export.orders");
  await ca.getByRole("button", { name: "Apply filters" }).click();
  const events = ca.getByRole("table", { name: "Audit events" });
  await expect(events).toContainText("management.export.orders");
  await expect(events).toContainText("Demo Regional Manager");
  await expectNoAxeViolations(ca);
});

test("staff access: an RM adds and removes an agent; only a CA may grant Regional Manager", async ({
  browser,
}, info) => {
  const rm = await as(browser, info, "management", SEED.regionalManager);
  await rm.goto("/management/staff");
  const roles = rm.getByLabel("Role", { exact: true });
  await expect(roles.locator("option")).toHaveText(["Kitchen Staff", "Kitchen Manager", "Delivery Agent"]);
  // The RM's own row has no controls (no self-escalation, MG-01).
  await expect(
    rm.getByRole("list", { name: "Roles of Demo Regional Manager" }).getByRole("button"),
  ).toHaveCount(0);

  const name = `TEST – E2E Agent ${Date.now() % 100000}`;
  await rm.getByLabel("Name").fill(name);
  await rm.getByLabel("Mobile number").fill(newTestMobile());
  await roles.selectOption("DELIVERY_AGENT");
  await rm.getByLabel("Reason").fill("E2E: new agent for the evening shift");
  await rm.getByRole("button", { name: "Add role" }).click();
  await expect(rm.getByRole("status").filter({ hasText: `${name} added as Delivery Agent` })).toBeVisible();
  const person = rm.getByRole("list", { name: `Roles of ${name}` });
  await expect(person).toContainText("Delivery Agent");
  await expectNoAxeViolations(rm);

  await person.getByRole("button", { name: "Remove role" }).click();
  await person.getByLabel(`Why are you removing this role from ${name}?`).fill("E2E cleanup");
  await person.getByRole("button", { name: "Remove role" }).click();
  await expect(rm.getByRole("list", { name: `Roles of ${name}` })).toHaveCount(0);

  const ca = await as(browser, info, "management", SEED.centralAdmin);
  await ca.goto("/management/global-staff");
  await expect(ca.getByLabel("Role", { exact: true }).locator("option")).toContainText(["Regional Manager"]);
  await expect(ca.getByRole("link", { name: "Staff & Access", exact: true })).toHaveCount(0);
  await expectNoAxeViolations(ca);
});

test("@devices management navigation works on tablets and phones", async ({ page }, info) => {
  test.skip(info.project.name === "phone-360", "DDR-114 (14): navigation on tablet and phone-390");
  await signIn(page, "management", SEED.regionalManager);
  for (const name of ["Orders & Exceptions", "Delivery Operations", "Staff & Access"]) {
    await openSection(page, name);
    await expectNoHorizontalScroll(page);
    await expectNoAxeViolations(page);
  }
});
