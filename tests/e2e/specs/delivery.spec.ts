import { expect, test, type Browser, type Page, type TestInfo } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, newTestMobile, registerCustomer, SEED, signIn } from "./helpers";

// Task 9 acceptance (DDR-113): the delivery flow from offer to Delivered with the customer's code, on the
// primary phone (phone-390), plus read-only screen checks on every device (`@devices`). The flow uses its
// own TEST agent (fixtures load-e2e-agent); the screen checks use the seed agent, which never goes online,
// so the two never compete for offers. Map tiles are blocked in E2E: the labelled fallback is checked.

const CSRF = { "X-DeliverIQ-CSRF": "1" };
const CHENNAI = { lat: 13.0835, lng: 80.271 };

async function as(browser: Browser, info: TestInfo, portal: string, mobile: string): Promise<Page> {
  const context = await browser.newContext({
    viewport: info.project.use.viewport ?? null,
    isMobile: info.project.use.isMobile,
    hasTouch: info.project.use.hasTouch,
  });
  const page = await context.newPage();
  await page.route(/tile\.openstreetmap\.org/, (route) => route.abort());
  await signIn(page, portal, mobile);
  return page;
}

test("@devices delivery screens without a delivery are labelled and accessible", async ({ browser }, info) => {
  const agent = await as(browser, info, "delivery", SEED.delivery);
  await expect(agent.getByText("Offline")).toBeVisible();
  await expect(agent.getByText("Go online to receive offers.")).toBeVisible();
  await expectNoHorizontalScroll(agent);
  await expectNoAxeViolations(agent);
  await expect(agent.getByRole("main")).toHaveScreenshot("delivery-home-offline.png");

  for (const [path, text] of [
    ["/delivery/active", "No active delivery"],
    ["/delivery/map", "No active delivery"],
    ["/delivery/history", "Your deliveries of the last 30 days"],
    ["/delivery/profile", "Profile photos are not available"],
  ] as const) {
    await agent.goto(path);
    await expect(agent.getByText(text).first()).toBeVisible();
    await expectNoHorizontalScroll(agent);
    await expectNoAxeViolations(agent);
  }
});

test("@phone an agent delivers a TEST order with the customer's code", async ({ browser }, info) => {
  test.skip(info.project.name !== "phone-390", "the full flow runs on the primary phone only");

  // Customer places a COD order; the kitchen accepts it.
  const customer = await (await browser.newContext()).newPage();
  await customer.goto("/customer/login");
  await registerCustomer(customer, newTestMobile(), "TEST E2E Customer");
  await expect(customer).toHaveURL(/\/customer$/);
  const address = await customer.request.post("/api/v1/me/addresses", {
    headers: CSRF,
    data: { label: "TEST – Home", address_line: "TEST – 1 Fixture Street", ...CHENNAI, make_default: true },
  });
  const menu = await customer.request.get(`/api/v1/menu/items?q=${encodeURIComponent("Synthetic Dish A")}`);
  const dish = ((await menu.json()) as { id: string; name: string; price_paise: number }[]).find(
    (d) => d.name === "TEST – Synthetic Dish A",
  );
  const placed = await customer.request.post("/api/v1/orders", {
    headers: { ...CSRF, "Idempotency-Key": crypto.randomUUID() },
    data: {
      lines: [{ menu_item_id: dish?.id, quantity: 5, unit_price_paise: dish?.price_paise }],
      payment_method: "COD",
      address_id: ((await address.json()) as { id: string }).id,
    },
  });
  expect(placed.status()).toBe(201);
  const orderId = ((await placed.json()) as { id: string }).id;
  const kitchen = await (await browser.newContext()).newPage();
  await signIn(kitchen, "kitchen", SEED.kitchenStaff);
  expect((await kitchen.request.post(`/api/v1/kitchen/orders/${orderId}/accept`, { headers: CSRF })).status()).toBe(200);

  // The agent goes online and accepts this order's offer (other tests' orders are rejected with a reason).
  const agent = await as(browser, info, "delivery", SEED.e2eAgent);
  try {
    await agent.getByRole("button", { name: "Go online" }).click();
    const offer = agent.getByRole("region", { name: "New delivery offer" });
    for (let attempt = 0; attempt < 6; attempt++) {
      await expect(offer).toBeVisible({ timeout: 20_000 });
      if (await offer.getByText(`Order ${orderId.slice(0, 8)}`).isVisible()) break;
      await offer.getByRole("button", { name: "Reject" }).click();
      await agent.getByLabel("Why are you rejecting this offer?").fill("E2E: not this test's order");
      await agent.getByRole("button", { name: "Reject offer" }).click();
    }
    await expect(offer.getByText(`Order ${orderId.slice(0, 8)}`)).toBeVisible();
    await expect(offer.getByText("The address is shown after you accept.")).toBeVisible();
    await expect(offer.getByTestId("offer-countdown")).toContainText("s left to answer");
    await expectNoAxeViolations(agent);
    await offer.getByRole("button", { name: "Accept" }).click();
    await expect(agent.getByText(/Deliver to:/)).toBeVisible();

    // Simulated GPS, then the map with its labelled fallback (tiles are blocked here).
    await agent.goto("/delivery/active");
    await agent.getByRole("button", { name: "Use simulated GPS" }).click();
    await expect(agent.getByText("Simulated GPS").first()).toBeVisible();
    await expectNoAxeViolations(agent);
    await agent.goto("/delivery/map");
    await expect(agent.getByText("Route: straight line (estimated, not road routing)")).toBeVisible();
    await expect(agent.getByRole("list", { name: "Places" })).toContainText("TEST – 1 Fixture Street");

    // Pickup is refused until the kitchen marks the order Ready.
    await agent.goto("/delivery/pickup");
    await expect(agent.getByRole("button", { name: "Picked up" })).toBeDisabled();
    const held = (await (await kitchen.request.get("/api/v1/kitchen/orders")).json()) as {
      held: { id: string; items: { id: string }[] }[];
    };
    const itemId = held.held.find((o) => o.id === orderId)?.items[0]?.id;
    await kitchen.request.post(`/api/v1/kitchen/orders/${orderId}/start`, { headers: CSRF });
    await kitchen.request.post(`/api/v1/kitchen/orders/${orderId}/items/${itemId}/status`, {
      headers: CSRF,
      data: { status: "PREPARED" },
    });
    await expect(agent.getByRole("button", { name: "Picked up" })).toBeEnabled({ timeout: 15_000 });
    await agent.getByRole("button", { name: "Picked up" }).click();
    await expect(agent.getByText(/Picked up\./)).toBeVisible();

    // The customer sees the code (never shown to the agent) and the labelled simulated position.
    await customer.goto(`/customer/orders/${orderId}`);
    const code = (await customer.getByTestId("delivery-code").textContent())?.trim() ?? "";
    expect(code).toMatch(/^\d{6}$/);
    await expect(customer.getByRole("region", { name: "On the way" })).toBeVisible();

    // A wrong code is refused by the backend; the right one completes the delivery.
    await agent.goto("/delivery/completion");
    await agent.getByRole("button", { name: "Cash collected" }).click();
    const input = agent.getByLabel("Customer's delivery code");
    await input.fill(code === "000000" ? "111111" : "000000");
    await agent.getByRole("button", { name: "Confirm delivery" }).click();
    await expect(agent.getByRole("alert")).toContainText("Wrong delivery code. 2 attempt(s) left.");
    await expectNoAxeViolations(agent);
    await input.fill(code);
    await agent.getByRole("button", { name: "Confirm delivery" }).click();
    await expect(agent.getByText("No active delivery").or(agent.getByText("Go online to receive offers"))).toBeVisible();
    await customer.reload();
    await expect(customer.getByTestId("order-status")).toHaveText("Delivered");
  } finally {
    await agent.request.put("/api/v1/delivery/me/availability", { headers: CSRF, data: { online: false } });
  }
});
