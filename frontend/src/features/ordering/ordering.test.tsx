import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Address, Cart, CartLine, Dish, MenuItem, Order, Serviceability } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

// Fixtures mirror the backend response shapes (generated schema); values are TEST data (DDR-107/110).
const CUSTOMER = me({
  permissions: [
    "customer.orders.read",
    "customer.profile.read",
    "customer.orders.place",
    "customer.orders.cancel",
  ],
});
const VISITOR = {
  "GET /api/v1/me": () => json({ code: "http_401" }, 401),
  "POST /api/v1/auth/trusted-login": () => json({ detail: "x" }, 401),
};
const DISH_A = "aaaaaaaa-0000-0000-0000-000000000001";
const ADDRESS = "adadadad-0000-0000-0000-000000000001";
const ORDER = "0e0e0e0e-0000-0000-0000-000000000001";
const LOCATION_KEY = "diq.customer.location";

function reach(serviceable = true): Serviceability {
  return {
    kitchen_location_is_synthetic: true,
    kitchen_name: "TEST – Chennai Kitchen",
    road_km: serviceable ? "2.80" : "21.00",
    road_km_estimated: true,
    road_max_km: "8.0",
    road_ok: serviceable,
    serviceable,
    straight_line_km: serviceable ? "2.00" : "15.00",
    straight_line_max_km: "6.0",
    straight_line_ok: serviceable,
  };
}

function menuItem(overrides: Partial<MenuItem> = {}): MenuItem {
  return {
    id: DISH_A,
    name: "TEST – Synthetic Dish A",
    description: "TEST – synthetic dish for workflow testing",
    category: "TEST – Category",
    image_url: null,
    image_is_placeholder: true,
    is_bestseller: false,
    is_test_fixture: true,
    is_veg: true,
    prep_time_minutes: 10,
    price_paise: 11100,
    spice_level: "TEST",
    ...overrides,
  };
}

function dish(): Dish {
  return { ...menuItem(), ingredients: ["TEST – Ingredient 1", "TEST – Ingredient 2"], customizations: [] };
}

const FILTERS = {
  categories: ["TEST – Category"],
  has_bestsellers: false,
  has_non_veg: false,
  has_veg: true,
  max_price_paise: 33300,
  min_price_paise: 11100,
  spice_levels: ["TEST"],
};

function address(): Address {
  return {
    id: ADDRESS,
    label: "TEST – Home",
    address_line: "TEST – 1 Fixture Street",
    created_at: "2026-11-12T10:00:00Z",
    is_default: true,
    lat: 13.0835,
    lng: 80.271,
    serviceability: reach(),
  };
}

function line(overrides: Partial<CartLine> = {}): CartLine {
  return {
    menu_item_id: DISH_A,
    name: "TEST – Synthetic Dish A",
    quantity: 5,
    available: true,
    cart_price_paise: 11100,
    charge_price_paise: 11100,
    is_test_fixture: true,
    price_changed: false,
    protected_until: "2026-11-12T10:30:00Z",
    ...overrides,
  };
}

function cart(overrides: Partial<Cart> = {}, lines: CartLine[] = [line()]): Cart {
  const subtotal = lines.reduce((n, l) => n + (l.charge_price_paise ?? l.cart_price_paise) * l.quantity, 0);
  return {
    lines,
    address_error: null,
    blockers: [],
    coupon_code: null,
    coupon_error: null,
    serviceability: reach(),
    bill: {
      food_subtotal_paise: subtotal,
      delivery_fee_paise: 4000,
      discount_paise: 0,
      minimum_food_subtotal_paise: 50000,
      minimum_met: subtotal >= 50000,
      payable_paise: subtotal + 4000,
      tax_note: "Prices include applicable taxes.",
    },
    ...overrides,
  };
}

function order(overrides: Partial<Order> = {}): Order {
  return {
    id: ORDER,
    agent_assigned: false,
    delivery_address: "TEST – 1 Fixture Street",
    delivery_fee_paise: 4000,
    discount_paise: 0,
    food_subtotal_paise: 55500,
    fulfilment_status: "PLACED",
    is_test_fixture: true,
    items: [
      {
        menu_item_id: DISH_A,
        item_name: "TEST – Synthetic Dish A",
        prep_status: "PENDING",
        quantity: 5,
        unit_price_paise: 11100,
      },
    ],
    payable_paise: 59500,
    payment: payment(),
    placed_at: "2026-11-12T10:00:00Z",
    road_km_estimated: true,
    special_instructions: null,
    status_label: "Order Placed",
    ...overrides,
  };
}

function payment(overrides: Partial<NonNullable<Order["payment"]>> = {}): NonNullable<Order["payment"]> {
  return {
    method: "SIM_UPI",
    status: "PENDING",
    amount_paise: 59500,
    sim_reference: "SIM-0001",
    simulated: true,
    ...overrides,
  };
}

function chooseLocation(lat = 13.0835, lng = 80.271) {
  localStorage.setItem(LOCATION_KEY, JSON.stringify({ lat, lng, label: "Current location", source: "gps" }));
}

function stubGeolocation(succeed: boolean) {
  const getCurrentPosition = vi.fn((ok: PositionCallback, fail: PositionErrorCallback) => {
    if (succeed) ok({ coords: { latitude: 13.0835, longitude: 80.271 } } as GeolocationPosition);
    else fail({ code: 1, message: "denied" } as GeolocationPositionError);
  });
  Object.defineProperty(navigator, "geolocation", { value: { getCurrentPosition }, configurable: true });
  return getCurrentPosition;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("location and menu (CU-01–CU-07)", () => {
  it("asks a visitor for a location first and shows the menu once it is serviceable", async () => {
    const geo = stubGeolocation(true);
    const api = mockApi({
      ...VISITOR,
      "GET /api/v1/serviceability": () => json(reach()),
      "GET /api/v1/menu/filters": () => json(FILTERS),
      "GET /api/v1/menu/items": () => json([menuItem()]),
    });
    renderAt("/customer/menu");
    expect(await screen.findByRole("heading", { name: "Choose your delivery location" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Dishes" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Use my current location" }));
    expect(geo).toHaveBeenCalledOnce();
    const dishes = await screen.findByRole("list", { name: "Dishes" });
    expect(within(dishes).getByRole("link", { name: "TEST – Synthetic Dish A" })).toHaveAttribute(
      "href",
      `/customer/menu/${DISH_A}`,
    );
    expect(within(dishes).getByTestId("test-badge")).toBeInTheDocument();
    expect(within(dishes).getByText("Image unavailable")).toBeInTheDocument();
    expect(screen.getByText(/road distance: estimated/)).toBeInTheDocument();
    // The location stays in the browser (DDR-110 (8)): no address call for a visitor.
    expect(JSON.parse(localStorage.getItem(LOCATION_KEY) ?? "null")).toMatchObject({ lat: 13.0835 });
    expect(api.calls.some((r) => r.url.includes("/me/addresses"))).toBe(false);
  });

  it("never invents a position when location access is denied", async () => {
    stubGeolocation(false);
    mockApi({ ...VISITOR });
    renderAt("/customer/menu");
    await userEvent.click(await screen.findByRole("button", { name: "Use my current location" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Location access was denied or unavailable");
    expect(localStorage.getItem(LOCATION_KEY)).toBeNull();
  });

  it("validates typed coordinates before using them", async () => {
    mockApi({
      ...VISITOR,
      "GET /api/v1/serviceability": () => json(reach()),
      "GET /api/v1/menu/filters": () => json(FILTERS),
      "GET /api/v1/menu/items": () => json([menuItem()]),
    });
    renderAt("/customer/menu");
    await userEvent.type(await screen.findByLabelText("Latitude"), "51.5");
    await userEvent.type(screen.getByLabelText("Longitude"), "-0.12");
    await userEvent.click(screen.getByRole("button", { name: "Use these coordinates" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a latitude and longitude in India");
    expect(localStorage.getItem(LOCATION_KEY)).toBeNull();
  });

  it("hides the menu outside the delivery area and gives only a message (DDR-110 (7))", async () => {
    chooseLocation(13.2, 80.4);
    const api = mockApi({ ...VISITOR, "GET /api/v1/serviceability": () => json(reach(false)) });
    renderAt("/customer/menu");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We can't deliver to this location yet. The kitchen delivers within 6.0 km straight-line and 8.0 km by road of TEST – Chennai Kitchen.",
    );
    expect(screen.getByText("Outside delivery area")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Dishes" })).not.toBeInTheDocument();
    expect(api.calls.some((r) => r.url.includes("/menu/items"))).toBe(false);
  });

  it("sends the chosen filters to the backend; options come from the data", async () => {
    chooseLocation();
    const api = mockApi({
      ...VISITOR,
      "GET /api/v1/serviceability": () => json(reach()),
      "GET /api/v1/menu/filters": () => json(FILTERS),
      "GET /api/v1/menu/items": (r) =>
        json(new URL(r.url).searchParams.get("q") === "nothing" ? [] : [menuItem()]),
    });
    renderAt("/customer/menu");
    await screen.findByRole("list", { name: "Dishes" });
    // No bestseller is flagged, so the bestseller filter is not offered (DDR-110 (2)).
    expect(screen.queryByLabelText("Bestsellers only")).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Non-vegetarian" })).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Spice level"), "TEST");
    await userEvent.selectOptions(screen.getByLabelText("Veg / non-veg"), "veg");
    await userEvent.type(screen.getByLabelText("Max price (₹)"), "2a00");
    await waitFor(() => {
      const last = new URL(api.calls.filter((r) => r.url.includes("/menu/items")).at(-1)?.url ?? "");
      expect(Object.fromEntries(last.searchParams)).toEqual({
        spice: "TEST",
        veg: "true",
        max_price_paise: "20000",
      });
    });
    await userEvent.type(screen.getByLabelText("Search dishes"), "nothing");
    expect(await screen.findByText("No dishes match these filters")).toBeInTheDocument();
  });

  it("shows an error state when the menu cannot be loaded", async () => {
    chooseLocation();
    mockApi({
      ...VISITOR,
      "GET /api/v1/serviceability": () => json(reach()),
      "GET /api/v1/menu/filters": () => json(FILTERS),
      "GET /api/v1/menu/items": () => json({ code: "http_500" }, 500),
    });
    renderAt("/customer/menu");
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
  });

  it("shows an error state when the delivery check fails", async () => {
    chooseLocation();
    mockApi({ ...VISITOR, "GET /api/v1/serviceability": () => json({ code: "http_500" }, 500) });
    renderAt("/customer/menu");
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
  });
});

describe("dish page (CU-08)", () => {
  it("asks a visitor to sign in instead of offering Add to cart", async () => {
    mockApi({ ...VISITOR, [`GET /api/v1/menu/items/${DISH_A}`]: () => json(dish()) });
    renderAt(`/customer/menu/${DISH_A}`);
    expect(await screen.findByRole("heading", { name: "TEST – Synthetic Dish A" })).toBeInTheDocument();
    expect(screen.getByText("TEST – Ingredient 1")).toBeInTheDocument();
    expect(screen.getByText("No customization options are set for this dish.")).toBeInTheDocument();
    expect(screen.getByText("Prices include applicable taxes.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add to cart" })).not.toBeInTheDocument();
    expect(within(screen.getByRole("article")).getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      `/customer/login?next=${encodeURIComponent(`/customer/menu/${DISH_A}`)}`,
    );
  });

  it("adds the chosen quantity to the persisted cart for a signed-in customer", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/menu/items/${DISH_A}`]: () => json(dish()),
      [`PUT /api/v1/cart/items/${DISH_A}`]: () => json(cart()),
      "GET /api/v1/me/addresses": () => json([address()]),
      "GET /api/v1/cart": () => json(cart()),
    });
    const router = renderAt(`/customer/menu/${DISH_A}`);
    const qty = await screen.findByLabelText("Quantity");
    await userEvent.clear(qty);
    await userEvent.type(qty, "5");
    await userEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/customer/cart"));
    const put = api.calls.find((r) => r.method === "PUT");
    expect(await put?.json()).toEqual({ quantity: 5 });
  });

  it("refuses a quantity outside 1–99 without calling the backend", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/menu/items/${DISH_A}`]: () => json(dish()),
    });
    renderAt(`/customer/menu/${DISH_A}`);
    const qty = await screen.findByLabelText("Quantity");
    await userEvent.clear(qty);
    await userEvent.type(qty, "100");
    await userEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a quantity from 1 to 99.");
    expect(api.calls.some((r) => r.method === "PUT")).toBe(false);
  });

  it("shows the backend refusal when the dish cannot be added", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/menu/items/${DISH_A}`]: () => json(dish()),
      [`PUT /api/v1/cart/items/${DISH_A}`]: () =>
        json({ code: "dish_unavailable", message: "not available" }, 422),
    });
    renderAt(`/customer/menu/${DISH_A}`);
    await userEvent.click(await screen.findByRole("button", { name: "Add to cart" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no longer available");
  });

  it("shows a not-found state for an unknown dish", async () => {
    mockApi({ ...VISITOR, [`GET /api/v1/menu/items/${DISH_A}`]: () => json({ code: "http_404" }, 404) });
    renderAt(`/customer/menu/${DISH_A}`);
    expect(await screen.findByText("This dish is not available")).toBeInTheDocument();
  });
});

function cartApi(current: () => Cart, extra: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    "GET /api/v1/me": () => json(CUSTOMER),
    "GET /api/v1/me/addresses": () => json([address()]),
    "GET /api/v1/cart": () => json(current()),
    ...extra,
  });
}

describe("cart and checkout (CU-11–CU-18)", () => {
  it("needs a session", async () => {
    mockApi({ ...VISITOR });
    const router = renderAt("/customer/cart");
    await waitFor(() => expect(router.state.location.pathname).toBe("/customer/login"));
  });

  it("shows the empty state", async () => {
    cartApi(() => cart({ blockers: ["cart_empty"] }, []));
    renderAt("/customer/cart");
    expect(await screen.findByText("Your cart is empty")).toBeInTheDocument();
  });

  it("quotes the bill for the default address and shows the minimum-order gap", async () => {
    const api = cartApi(() =>
      cart({ blockers: ["below_minimum"] }, [line({ quantity: 2, charge_price_paise: 11100 })]),
    );
    renderAt("/customer/cart");
    expect(await screen.findByTestId("minimum-gap")).toHaveTextContent(
      "Add ₹278 more to reach the ₹500 minimum.",
    );
    expect(screen.getByRole("radio", { name: /TEST – Home \(default\)/ })).toBeChecked();
    const bill = screen.getByRole("region", { name: "Bill" });
    expect(bill).toHaveTextContent("Food subtotal₹222");
    expect(bill).toHaveTextContent("Prices include applicable taxes.");
    expect(within(screen.getByRole("list", { name: "Before you can order" })).getByText(/minimum order/));
    expect(screen.getByRole("button", { name: /Place order/ })).toBeDisabled();
    await waitFor(() =>
      expect(api.calls.some((r) => new URL(r.url).searchParams.get("address_id") === ADDRESS)).toBe(true),
    );
  });

  it("asks the customer to accept a changed price (DDR-110 (6))", async () => {
    const changed = cart({ blockers: ["price_changed"] }, [
      line({ price_changed: true, cart_price_paise: 11100, charge_price_paise: 12000 }),
    ]);
    const api = cartApi(() => changed, {
      [`POST /api/v1/cart/items/${DISH_A}/accept-price`]: () => json(cart()),
    });
    renderAt("/customer/cart");
    expect(await screen.findByText("The price changed from ₹111 to ₹120.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Place order/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Accept new price" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/accept-price"))).toBe(true));
  });

  it("removes unavailable dishes only after confirmation", async () => {
    const api = cartApi(
      () => cart({ blockers: ["dish_unavailable"] }, [line({ available: false, charge_price_paise: null })]),
      { "POST /api/v1/cart/remove-unavailable": () => json(cart({}, [])) },
    );
    renderAt("/customer/cart");
    expect(await screen.findByText(/TEST – Synthetic Dish A is no longer available/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove unavailable dishes" }));
    expect(api.calls.some((r) => r.url.endsWith("/remove-unavailable"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/remove-unavailable"))).toBe(true));
  });

  it("shows the coupon refusal and does not send a refused coupon with the order", async () => {
    const api = cartApi(() => cart({ coupon_code: "NOPE", coupon_error: "coupon_unknown" }));
    renderAt("/customer/cart");
    await userEvent.type(await screen.findByLabelText("Coupon code"), "NOPE");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("This coupon code is not valid.")).toBeInTheDocument();
    await waitFor(() =>
      expect(api.calls.some((r) => new URL(r.url).searchParams.get("coupon_code") === "NOPE")).toBe(true),
    );
  });

  it("applies a coupon and shows the discount", async () => {
    cartApi(() => {
      const c = cart({ coupon_code: "TEST50" });
      return { ...c, bill: { ...c.bill, discount_paise: 5000, payable_paise: c.bill.payable_paise - 5000 } };
    });
    renderAt("/customer/cart");
    expect(await screen.findByText("Coupon TEST50 applied.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Bill" })).toHaveTextContent("Coupon− ₹50");
  });

  it("places the order with an Idempotency-Key and the prices the customer saw", async () => {
    const api = cartApi(() => cart(), {
      "POST /api/v1/orders": () => json(order(), 201),
      [`GET /api/v1/orders/${ORDER}`]: () => json(order()),
    });
    const router = renderAt("/customer/cart");
    await userEvent.click(await screen.findByRole("radio", { name: "Cash on Delivery" }));
    await userEvent.type(screen.getByLabelText("Special instructions (optional)"), "Ring twice");
    expect(screen.getByText("10 / 250 characters")).toBeInTheDocument();
    expect(screen.getByText("This order uses TEST dishes.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Place order · ₹595" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/customer/orders/${ORDER}`));
    const post = api.calls.find((r) => r.method === "POST" && r.url.endsWith("/api/v1/orders"));
    expect(post?.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await post?.json()).toEqual({
      lines: [{ menu_item_id: DISH_A, quantity: 5, unit_price_paise: 11100 }],
      payment_method: "COD",
      address_id: ADDRESS,
      special_instructions: "Ring twice",
      coupon_code: null,
    });
  });

  it("explains a price change refused at placement and uses a new key for the retry", async () => {
    const api = cartApi(() => cart(), {
      "POST /api/v1/orders": () =>
        json({ code: "price_changed", message: "prices changed", price_changes: [] }, 409),
    });
    renderAt("/customer/cart");
    const place = await screen.findByRole("button", { name: /Place order/ });
    await userEvent.click(place);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A price has changed since you added the dish.",
    );
    await userEvent.click(place);
    await waitFor(() =>
      expect(api.calls.filter((r) => r.method === "POST" && r.url.endsWith("/orders"))).toHaveLength(2),
    );
    const [first, second] = api.calls.filter((r) => r.method === "POST" && r.url.endsWith("/orders"));
    expect(first?.headers.get("Idempotency-Key")).not.toBe(second?.headers.get("Idempotency-Key"));
  });
});

describe("orders (CU-19–CU-21)", () => {
  it("shows the labelled payment simulator for a prepaid order and applies the stated result", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/orders/${ORDER}`]: () => json(order()),
      [`POST /api/v1/orders/${ORDER}/payment/simulate`]: () =>
        json(
          order({
            fulfilment_status: "CANCELLED",
            status_label: "Cancelled",
            payment: payment({ status: "FAILED" }),
          }),
        ),
    });
    renderAt(`/customer/orders/${ORDER}`);
    const sim = await screen.findByRole("region", { name: "Payment simulator" });
    expect(sim).toHaveTextContent("This is a simulation: no real money moves.");
    expect(sim).toHaveTextContent("UPI (Simulation) · ₹595 · reference SIM-0001");
    expect(screen.getByText("Test order")).toBeInTheDocument();
    await userEvent.click(within(sim).getByRole("button", { name: "Simulate failure" }));
    expect(await screen.findByTestId("order-status")).toHaveTextContent("Cancelled");
    expect(screen.queryByRole("region", { name: "Payment simulator" })).not.toBeInTheDocument();
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ outcome: "FAILED" });
  });

  it("has no simulator for Cash on Delivery", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/orders/${ORDER}`]: () =>
        json(
          order({
            fulfilment_status: "PENDING_KITCHEN",
            status_label: "Awaiting kitchen acceptance",
            payment: payment({ method: "COD", status: "COLLECTION_PENDING", sim_reference: null }),
          }),
        ),
    });
    renderAt(`/customer/orders/${ORDER}`);
    expect(await screen.findByTestId("order-status")).toHaveTextContent("Awaiting kitchen acceptance");
    expect(screen.queryByRole("region", { name: "Payment simulator" })).not.toBeInTheDocument();
    expect(screen.getByText("Cash on Delivery: Collection pending")).toBeInTheDocument();
  });

  it("cancels only after confirmation and says a prepaid payment is refunded", async () => {
    const pending = order({
      fulfilment_status: "PENDING_KITCHEN",
      status_label: "Awaiting kitchen acceptance",
      payment: payment({ status: "SUCCEEDED" }),
    });
    const api = mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/orders/${ORDER}`]: () => json(pending),
      [`POST /api/v1/orders/${ORDER}/cancel`]: () =>
        json({
          ...pending,
          fulfilment_status: "CANCELLED",
          status_label: "Cancelled",
          payment: payment({ status: "REFUNDED" }),
        }),
    });
    renderAt(`/customer/orders/${ORDER}`);
    await userEvent.click(await screen.findByRole("button", { name: "Cancel order" }));
    expect(screen.getByText(/The simulated payment is refunded in full/)).toBeInTheDocument();
    expect(api.calls.some((r) => r.method === "POST")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    expect(await screen.findByText("UPI (Simulation): Refunded")).toBeInTheDocument();
    expect(screen.getByTestId("order-status")).toHaveTextContent("Cancelled");
    expect(screen.queryByRole("button", { name: "Cancel order" })).not.toBeInTheDocument();
  });

  it("shows the backend refusal when cancellation is no longer allowed", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/orders/${ORDER}`]: () =>
        json(order({ fulfilment_status: "PENDING_KITCHEN", status_label: "Awaiting kitchen acceptance" })),
      [`POST /api/v1/orders/${ORDER}/cancel`]: () =>
        json({ code: "http_409", message: "the kitchen has already accepted this order" }, 409),
    });
    renderAt(`/customer/orders/${ORDER}`);
    await userEvent.click(await screen.findByRole("button", { name: "Cancel order" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("the kitchen has already accepted this order");
  });

  it("lists orders, and shows empty, not-found and denied states", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      "GET /api/v1/orders": () => json([order()]),
    });
    renderAt("/customer/orders");
    expect(await screen.findByRole("link", { name: "Order 0e0e0e0e" })).toHaveAttribute(
      "href",
      `/customer/orders/${ORDER}`,
    );
    expect(screen.getByText(/5 item\(s\) · ₹595/)).toBeInTheDocument();
  });

  it("shows the empty orders state", async () => {
    mockApi({ "GET /api/v1/me": () => json(CUSTOMER), "GET /api/v1/orders": () => json([]) });
    renderAt("/customer/orders");
    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
  });

  it("shows not found for another customer's order", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/orders/${ORDER}`]: () => json({ code: "http_404" }, 404),
    });
    renderAt(`/customer/orders/${ORDER}`);
    expect(await screen.findByText("Order not found")).toBeInTheDocument();
  });

  it("shows a denied state when the backend refuses", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      "GET /api/v1/orders": () => json({ code: "http_403" }, 403),
    });
    renderAt("/customer/orders");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });

  it("guards the order detail route for visitors", async () => {
    mockApi({ ...VISITOR });
    const router = renderAt(`/customer/orders/${ORDER}`);
    await waitFor(() => expect(router.state.location.pathname).toBe("/customer/login"));
  });

  it("shows a loading state while the order loads", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      [`GET /api/v1/orders/${ORDER}`]: () => new Promise<Response>(() => undefined),
    });
    renderAt(`/customer/orders/${ORDER}`);
    expect(await screen.findByText("Loading order…")).toBeInTheDocument();
  });
});
