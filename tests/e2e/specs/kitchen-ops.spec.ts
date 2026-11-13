import { expect, test, type Browser, type Locator, type Page, type TestInfo } from "@playwright/test";

import { expectNoAxeViolations, newTestMobile, registerCustomer, SEED, signIn } from "./helpers";

// Task 8 acceptance (DDR-111, DDR-112): kitchen staff run a TEST order from Incoming to Ready, the
// manager adjusts labelled test stock and ends the order, and dish unavailability needs RM approval.
// Runs on `tablet` and `kds` (`@kitchen`). Both projects share one kitchen, so every order this
// spec accepts is ended ("Cannot fulfil") and every change is undone: capacity, stock, agent offers
// and the menu are left as found. Kitchen mode is never changed here (customer specs run in
// parallel); Paused is proven by the integration suite.

const CSRF = { "X-DeliverIQ-CSRF": "1" };
const CHENNAI = { lat: 13.0835, lng: 80.271 }; // fixture seed address (fixtures.py)

async function as(browser: Browser, info: TestInfo, portal: string, mobile: string): Promise<Page> {
  const context = await browser.newContext({ viewport: info.project.use.viewport ?? null });
  const page = await context.newPage();
  await signIn(page, portal, mobile);
  return page;
}

/** A fresh TEST customer places a COD order for 5 × Dish A through the API; returns the order id. */
async function placeTestOrder(browser: Browser): Promise<string> {
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
  return id;
}

function card(page: Page, orderId: string): Locator {
  return page.getByRole("article", { name: `Order ${orderId.slice(0, 8)}` });
}

test("@kitchen kitchen staff take a TEST order from Incoming to Ready; the manager ends it", async ({
  browser,
}, info) => {
  const orderId = await placeTestOrder(browser);
  const ks = await as(browser, info, "kitchen", SEED.kitchenStaff);
  await ks.goto("/kitchen/live-orders");
  const incoming = card(ks, orderId);
  await expect(incoming).toContainText("Incoming");
  await expect(incoming.getByText("Test order")).toBeVisible();
  await expect(ks.getByTestId("poll-note")).toContainText("Updates every 10 s");
  await expectNoAxeViolations(ks);

  await incoming.getByRole("button", { name: "Accept" }).click();
  const accepted = ks.getByRole("list", { name: "Accepted orders in FIFO order" }).getByRole("article", {
    name: `Order ${orderId.slice(0, 8)}`,
  });
  await expect(accepted).toContainText("Accepted");
  await expect(accepted).toContainText("recipe v1");
  await expect(accepted.getByText(/Offered to|Awaiting agent/)).toBeVisible();

  await ks.goto("/kitchen/preparation");
  const prep = card(ks, orderId);
  await prep.getByRole("button", { name: "Start order" }).click();
  await expect(prep).toContainText("Preparing");
  await expect(prep.getByRole("button", { name: "Cannot fulfil" })).toHaveCount(0); // KM only
  await prep.getByRole("button", { name: "Mark TEST – Synthetic Dish A Prepared" }).click();
  await expect(prep).toContainText("Ready for Pickup");
  await expect(ks.getByRole("heading", { name: /^Ready for Pickup \(\d+\)$/ })).toBeVisible();
  await expectNoAxeViolations(ks);

  // The manager ends the order so no capacity, stock or agent offer is left held.
  const km = await as(browser, info, "kitchen", SEED.kitchenManager);
  await km.goto("/kitchen/preparation");
  const ready = card(km, orderId);
  await ready.getByRole("button", { name: "Cannot fulfil" }).click();
  await ready.getByLabel("Why can this order not be fulfilled?").fill("E2E test cleanup");
  await ready.getByRole("button", { name: "Reject order" }).click();
  await expect(card(km, orderId)).toHaveCount(0);
});

test("@kitchen an incoming order is rejected with a reason", async ({ browser }, info) => {
  const orderId = await placeTestOrder(browser);
  const ks = await as(browser, info, "kitchen", SEED.kitchenStaff);
  await ks.goto("/kitchen/live-orders");
  const incoming = card(ks, orderId);
  await incoming.getByRole("button", { name: "Reject" }).click();
  await incoming.getByLabel("Why is this order rejected?").fill("E2E: out of packaging");
  await expectNoAxeViolations(ks);
  await incoming.getByRole("button", { name: "Reject order" }).click();
  await expect(card(ks, orderId)).toHaveCount(0);
});

test("@kitchen the manager sees labelled test stock and test-default settings", async ({ browser }, info) => {
  const km = await as(browser, info, "kitchen", SEED.kitchenManager);
  await km.goto("/kitchen/inventory");
  const row = km.getByTestId("stock-row").filter({ hasText: "TEST – Ingredient 6" });
  await expect(row.getByText("Test stock")).toBeVisible();
  await expect(km.getByText(/Opening stock is test-only/)).toBeVisible();
  // A reasoned adjustment and its reversal leave the stock as found.
  for (const delta of ["1", "-1"]) {
    await row.getByRole("button", { name: "Adjust stock of TEST – Ingredient 6" }).click();
    await row.getByLabel("Change in g").fill(delta);
    await row.getByLabel("Reason for the adjustment").fill(`E2E adjustment ${delta}`);
    await row.getByRole("button", { name: "Save adjustment" }).click();
    await expect(row.getByRole("button", { name: "Adjust stock of TEST – Ingredient 6" })).toBeVisible();
  }
  await expectNoAxeViolations(km);

  await km.goto("/kitchen/settings");
  await expect(km.getByText("Test default, not a final value (DDR-42 open)")).toHaveCount(2);
  await expect(km.getByRole("button", { name: "Review and save" })).toBeDisabled();
  await expectNoAxeViolations(km);
  await expect(km.getByRole("main")).toHaveScreenshot("kitchen-settings.png");

  const ks = await as(browser, info, "kitchen", SEED.kitchenStaff);
  await ks.goto("/kitchen/inventory");
  await expect(ks.getByRole("heading", { name: /^Low-stock alerts/ })).toBeVisible();
  await expect(ks.getByRole("button", { name: /Adjust stock/ })).toHaveCount(0);
  await expect(ks.getByRole("link", { name: "Settings" })).toHaveCount(0);
});

test("@kitchen dish unavailability needs Regional Manager approval", async ({ browser }, info) => {
  // One dish per project, so the two projects never race for the same pending request.
  const dish = info.project.name === "kds" ? "TEST – Synthetic Dish C" : "TEST – Synthetic Dish B";
  const ks = await as(browser, info, "kitchen", SEED.kitchenStaff);
  const rm = await as(browser, info, "management", SEED.regionalManager);
  const onMenu = async () =>
    ((await (await ks.request.get("/api/v1/menu/items")).json()) as { name: string }[]).some((d) => d.name === dish);

  async function request(button: string, reason: string) {
    await ks.goto("/kitchen/inventory");
    const item = ks.getByRole("list", { name: "Kitchen dishes" }).getByRole("listitem").filter({ hasText: dish });
    await item.getByRole("button", { name: button }).click();
    await item.getByRole("textbox").fill(reason);
    await item.getByRole("button", { name: "Send request" }).click();
    await expect(ks.getByText(`Request sent for ${dish}.`)).toBeVisible();
  }

  async function approve() {
    await rm.goto("/management/dish-availability");
    const pending = rm
      .getByTestId("availability-request")
      .filter({ hasText: dish })
      .filter({ hasText: "Waiting for decision" });
    await expectNoAxeViolations(rm);
    await pending.getByRole("button", { name: "Approve" }).click();
    await expect(pending).toHaveCount(0);
  }

  await request("Request unavailable", "E2E: ingredient spoiled");
  expect(await onMenu()).toBe(true); // a request alone never changes the menu
  await expectNoAxeViolations(ks);
  await approve();
  await expect.poll(onMenu).toBe(false);

  await request("Request available again", "E2E: restocked");
  await approve();
  await expect.poll(onMenu).toBe(true);
});
