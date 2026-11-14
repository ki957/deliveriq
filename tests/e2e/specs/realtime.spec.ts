import { expect, test, type Browser, type Page, type TestInfo } from "@playwright/test";

import { expectNoAxeViolations, newTestMobile, registerCustomer, SEED, signIn } from "./helpers";

// Task 11 acceptance (DDR-115 (14)): screens update from socket hints without a reload, and a dropped
// socket falls back to polling. Polling is off while the socket is live, so an update inside 5 s here
// can only come from a hint (the fallback interval is 10 s). Every TEST order is ended. The customer's
// live "Agent Assigned" is proven in delivery.spec.ts, whose TEST agent is the only one this suite puts
// online (two online agents would take each other's offers).

const CSRF = { "X-DeliverIQ-CSRF": "1" };
const CHENNAI = { lat: 13.0835, lng: 80.271 }; // fixture seed address (fixtures.py)
const HINT_MS = 5_000;

async function as(browser: Browser, info: TestInfo, portal: string, mobile: string): Promise<Page> {
  const context = await browser.newContext({ viewport: info.project.use.viewport ?? null });
  const page = await context.newPage();
  await signIn(page, portal, mobile);
  return page;
}

/** A fresh TEST customer signed in on `page`, with a default address; returns the address id. */
async function newCustomer(page: Page): Promise<string> {
  await page.goto("/customer/login");
  await registerCustomer(page, newTestMobile(), "TEST E2E Customer");
  await expect(page).toHaveURL(/\/customer$/);
  const address = await page.request.post("/api/v1/me/addresses", {
    headers: CSRF,
    data: { label: "TEST – Home", address_line: "TEST – 1 Fixture Street", ...CHENNAI, make_default: true },
  });
  expect(address.status()).toBe(201);
  return ((await address.json()) as { id: string }).id;
}

/** A COD order for 5 × TEST Dish A, placed through the API from the customer's page. */
async function placeOrder(page: Page, addressId: string): Promise<string> {
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
      address_id: addressId,
    },
  });
  expect(order.status()).toBe(201);
  return ((await order.json()) as { id: string }).id;
}

async function endOrder(km: Page, orderId: string): Promise<void> {
  const r = await km.request.post(`/api/v1/kitchen/orders/${orderId}/reject`, {
    headers: CSRF,
    data: { reason: "E2E test cleanup" },
  });
  expect([200, 409]).toContain(r.status());
}

test("the kitchen board shows a new order live, without a reload", async ({ browser }, info) => {
  const ks = await as(browser, info, "kitchen", SEED.kitchenStaff);
  await ks.goto("/kitchen/live-orders");
  await expect(ks.getByTestId("poll-note")).toContainText("Live ·");

  const context = await browser.newContext();
  const customer = await context.newPage();
  const orderId = await placeOrder(customer, await newCustomer(customer));
  const card = ks.getByRole("article", { name: `Order ${orderId.slice(0, 8)}` });
  await expect(card).toContainText("Incoming", { timeout: HINT_MS });
  await expectNoAxeViolations(ks);

  // The customer's notifications page is open; the kitchen's rejection arrives live (DDR-115 (10)).
  await customer.goto("/customer/notifications");
  await expect(customer.getByTestId("notification-channels")).toContainText("SMS: Not configured (DDR-40)");
  const km = await as(browser, info, "kitchen", SEED.kitchenManager);
  await endOrder(km, orderId);
  await expect(card).toHaveCount(0, { timeout: HINT_MS });
  await expect(customer.getByRole("list", { name: "Notifications" })).toContainText(
    `The kitchen could not take your order ${orderId.slice(0, 8)}.`,
    { timeout: HINT_MS },
  );
  await expect(customer.getByTestId("notifications-bell")).toHaveAccessibleName(/Notifications, \d+ unread/);
  await expectNoAxeViolations(customer);
  // The Kitchen Manager has a Notifications page (low stock, KI-23).
  await km.goto("/kitchen/notifications");
  await expect(km.getByRole("heading", { level: 1, name: "Notifications" })).toBeVisible();
  await context.close();
});

test("a blocked socket falls back to polling and says so", async ({ page }) => {
  await page.routeWebSocket("**/api/v1/realtime", (ws) => ws.close({ code: 1013 }));
  await signIn(page, "kitchen", SEED.kitchenStaff);
  await page.goto("/kitchen/live-orders");
  await expect(page.getByTestId("poll-note")).toContainText("Live updates paused · updates every 10 s");
  await expectNoAxeViolations(page);
});
