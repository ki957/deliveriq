import { expect, test, type Locator, type Page } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, newTestMobile, registerCustomer } from "./helpers";

// Task 6 acceptance: location → serviceable menu → dish → sign-in → cart → coupon → place → simulated
// payment, on desktop, both phones and the tablet (`@devices`). TEST dishes only (DDR-107, DDR-110).
// Every test registers its own TEST customer, so parallel projects never share a persisted cart.

const CHENNAI = { latitude: 13.0835, longitude: 80.271 }; // the fixture seed address (fixtures.py)
const DISH_A = "TEST – Synthetic Dish A"; // ₹111, published by `make fixtures`
const CSRF = { "X-DeliverIQ-CSRF": "1" };

/** Element screenshot with the fixed phone/tablet bottom bar hidden (it would overlap the element). */
async function screenshot(page: Page, target: Locator, name: string): Promise<void> {
  const style = await page.addStyleTag({
    content: 'nav[aria-label$="quick navigation"] { visibility: hidden; }',
  });
  await expect(target).toHaveScreenshot(name);
  await style.evaluate((node) => (node as Element).remove());
}

test.use({ geolocation: CHENNAI, permissions: ["geolocation"] });

test("@devices a visitor finds the menu, signs up and pays by simulated UPI", async ({ page }) => {
  await page.goto("/customer/menu");
  await expect(page.getByRole("heading", { name: "Choose your delivery location" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Dishes" })).toHaveCount(0);
  await expectNoAxeViolations(page);

  await page.getByRole("button", { name: "Use my current location" }).click();
  await expect(page.getByText("We deliver here")).toBeVisible();
  await expect(page.getByText("road distance: estimated")).toBeVisible();
  // The dish list grows with every recipe-workflow run, so search to one dish and screenshot the filters.
  await page.getByLabel("Search dishes").fill("Synthetic Dish A");
  const dishes = page.getByRole("list", { name: "Dishes" });
  await expect(dishes.getByRole("listitem")).toHaveCount(1);
  await expect(dishes.getByTestId("test-badge")).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectNoAxeViolations(page);
  await screenshot(page, page.getByRole("search", { name: "Menu filters" }), "menu-filters.png");

  await dishes.getByRole("link", { name: DISH_A }).click();
  const dish = page.getByRole("article");
  await expect(dish.getByRole("heading", { level: 1, name: DISH_A })).toBeVisible();
  await expect(dish.getByRole("button", { name: "Add to cart" })).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await expectNoAxeViolations(page);
  await screenshot(page, dish, "dish-visitor.png");

  await dish.getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/customer\/login\?next=/);
  await registerCustomer(page, newTestMobile(), "TEST E2E Customer");
  await expect(page).toHaveURL(/\/customer\/menu\/[0-9a-f-]{36}$/);

  await page.getByLabel("Quantity").fill("5");
  await page.getByRole("button", { name: "Add to cart" }).click();
  await expect(page).toHaveURL(/\/customer\/cart$/);
  await expect(page.getByRole("list", { name: "Before you can order" })).toContainText(
    "Choose a delivery address.",
  );
  const place = page.getByRole("button", { name: /^Place order/ });
  await expect(place).toBeDisabled();

  // A new customer has no address: save one from the browser's location.
  await page.getByRole("button", { name: "Add an address" }).click();
  await page.getByLabel("Label").fill("TEST – Home");
  await page.getByLabel("Address", { exact: true }).fill("TEST – 1 Fixture Street, Chennai");
  await page.getByRole("button", { name: "Use my current location" }).click();
  await expect(page.getByLabel("Latitude")).toHaveValue("13.083500");
  await page.getByRole("button", { name: "Save address" }).click();
  await expect(page.getByRole("radio", { name: /TEST – Home/ })).toBeChecked();
  await expect(page.getByText("We deliver here")).toBeVisible();

  await page.getByLabel("Coupon code").fill("TEST50");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText("Coupon TEST50 applied.")).toBeVisible();
  const bill = page.getByRole("region", { name: "Bill" });
  await expect(bill).toContainText("Food subtotal₹555");
  await expect(bill).toContainText("Coupon− ₹50");
  await expect(page.getByText("This order uses TEST dishes.")).toBeVisible();
  await expect(place).toBeEnabled();
  await expectNoHorizontalScroll(page);
  await expectNoAxeViolations(page);
  await screenshot(page, bill, "cart-bill.png");

  await place.click();
  await expect(page).toHaveURL(/\/customer\/orders\/[0-9a-f-]{36}$/);
  const simulator = page.getByRole("region", { name: "Payment simulator" });
  await expect(simulator).toContainText("This is a simulation: no real money moves.");
  await expect(page.getByText("Test order").first()).toBeVisible();
  await expectNoAxeViolations(page);

  await simulator.getByRole("button", { name: "Simulate success" }).click();
  await expect(page.getByTestId("order-status")).toHaveText("Awaiting kitchen acceptance");
  await expect(simulator).toHaveCount(0);
  const summary = page.getByRole("region", { name: "Bill and delivery" });
  await expect(summary).toContainText("UPI (Simulation): Succeeded");
  await expectNoHorizontalScroll(page);
  await expectNoAxeViolations(page);
  await screenshot(page, summary, "order-paid.png");
});

/** Register a new customer, then set up an address and a 5 × Dish A cart through the API. */
async function customerWithCart(page: Page): Promise<void> {
  await page.goto("/customer/login");
  await registerCustomer(page, newTestMobile(), "TEST E2E Customer");
  await expect(page).toHaveURL(/\/customer$/);
  const address = await page.request.post("/api/v1/me/addresses", {
    headers: CSRF,
    data: {
      label: "TEST – Home",
      address_line: "TEST – 1 Fixture Street, Chennai",
      lat: CHENNAI.latitude,
      lng: CHENNAI.longitude,
      make_default: true,
    },
  });
  expect(address.status()).toBe(201);
  const menu = await page.request.get(`/api/v1/menu/items?q=${encodeURIComponent("Synthetic Dish A")}`);
  const dish = ((await menu.json()) as { id: string; name: string }[]).find((d) => d.name === DISH_A);
  expect(dish, "Dish A must be published by `make fixtures`").toBeDefined();
  const line = await page.request.put(`/api/v1/cart/items/${dish?.id}`, {
    headers: CSRF,
    data: { quantity: 5 },
  });
  expect(line.status()).toBe(200);
  await page.goto("/customer/cart");
}

test("a cash-on-delivery order goes straight to the kitchen and can be cancelled before acceptance", async ({
  page,
}) => {
  await customerWithCart(page);
  await page.getByRole("radio", { name: "Cash on Delivery" }).check();
  await page.getByRole("button", { name: /^Place order/ }).click();
  await expect(page).toHaveURL(/\/customer\/orders\/[0-9a-f-]{36}$/);
  await expect(page.getByTestId("order-status")).toHaveText("Awaiting kitchen acceptance");
  await expect(page.getByRole("region", { name: "Payment simulator" })).toHaveCount(0);
  await expect(page.getByText("Cash on Delivery: Collection pending")).toBeVisible();

  await page.getByRole("button", { name: "Cancel order" }).click();
  await expect(page.getByText(/You can cancel only until the kitchen accepts it/)).toBeVisible();
  await expectNoAxeViolations(page);
  await page.getByRole("button", { name: "Confirm cancellation" }).click();
  await expect(page.getByTestId("order-status")).toHaveText("Cancelled");
  await expect(page.getByRole("button", { name: "Cancel order" })).toHaveCount(0);

  await page.goto("/customer/orders");
  await expect(page.getByRole("listitem").filter({ hasText: "Cancelled" })).toHaveCount(1);
});

test("a failed simulated payment cancels the order", async ({ page }) => {
  await customerWithCart(page);
  await page.getByRole("button", { name: /^Place order/ }).click();
  const simulator = page.getByRole("region", { name: "Payment simulator" });
  await simulator.getByRole("button", { name: "Simulate failure" }).click();
  await expect(page.getByTestId("order-status")).toHaveText("Cancelled");
  await expect(page.getByText("UPI (Simulation): Failed")).toBeVisible();
  await expect(simulator).toHaveCount(0);
});

test("outside the delivery area the menu is not shown", async ({ page }) => {
  await page.goto("/customer/menu");
  await page.getByLabel("Latitude").fill("13.5");
  await page.getByLabel("Longitude").fill("80.9");
  await page.getByRole("button", { name: "Use these coordinates" }).click();
  await expect(page.getByRole("alert")).toContainText("We can't deliver to this location yet.");
  await expect(page.getByText("Outside delivery area")).toBeVisible();
  await expect(page.getByRole("list", { name: "Dishes" })).toHaveCount(0);
  await expectNoAxeViolations(page);
});
