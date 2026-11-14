import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { AvailabilityRequest, KitchenOrder, KitchenQueue, KitchenSettings, Stock } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

// Fixtures mirror the generated schema; values are TEST data (DDR-107, DDR-111).
const KITCHEN = "k1k1k1k1-0000-0000-0000-000000000001";
const SHARED = [
  "kitchen.orders.view",
  "kitchen.orders.process",
  "kitchen.low_stock.view",
  "kitchen.unavailability.request",
];
const KS = me({
  roles: [{ role: "KITCHEN_STAFF", region_id: "r1", kitchen_id: KITCHEN }],
  permissions: SHARED,
  portals: ["kitchen"],
});
const KM = me({
  roles: [{ role: "KITCHEN_MANAGER", region_id: "r1", kitchen_id: KITCHEN }],
  permissions: [
    ...SHARED,
    "kitchen.inventory.view",
    "kitchen.stock.adjust",
    "kitchen.ingredients.manage",
    "kitchen.mode.change",
    "kitchen.orders.reject_accepted",
  ],
  portals: ["kitchen"],
});
const RM = me({
  roles: [{ role: "REGIONAL_MANAGER", region_id: "r1", kitchen_id: null }],
  permissions: ["management.unavailability.approve", "management.operations.view"],
  portals: ["management"],
});

const ITEM: KitchenOrder["items"][number] = {
  id: "1a1a1a1a-0000-0000-0000-000000000001",
  menu_item_id: "m1",
  item_name: "TEST – Synthetic Dish A",
  quantity: 5,
  prep_status: "PENDING",
  recipe_version_id: null,
  recipe_version: null,
};

function order(overrides: Partial<KitchenOrder> = {}): KitchenOrder {
  return {
    id: "0a0a0a0a-0000-0000-0000-000000000001",
    fulfilment_status: "PENDING_KITCHEN",
    status_label: "Incoming",
    is_test_fixture: true,
    special_instructions: "Less oil",
    payment_method: "COD",
    placed_at: "2026-11-12T10:00:00Z",
    queued_at: "2026-11-12T10:00:00Z",
    accepted_at: null,
    overdue: false,
    items: [ITEM],
    assignment: null,
    ...overrides,
  };
}

function queue(overrides: Partial<KitchenQueue> = {}): KitchenQueue {
  return {
    kitchen_id: KITCHEN,
    kitchen_name: "TEST – Chennai Kitchen",
    intake: { mode: "NORMAL", capacity: 10, active_orders: 2, accepting: true, refusal: null },
    acceptance_timeout_minutes: 5,
    incoming: [],
    held: [],
    can_process: true,
    can_reject_accepted: false,
    ...overrides,
  };
}

function held(
  id: string,
  status: KitchenOrder["fulfilment_status"],
  label: string,
  extra: Partial<KitchenOrder> = {},
) {
  return order({
    id,
    fulfilment_status: status,
    status_label: label,
    accepted_at: "2026-11-12T10:05:00Z",
    items: [
      {
        ...ITEM,
        recipe_version_id: "v1",
        recipe_version: 1,
        prep_status: status === "ACCEPTED" ? "PENDING" : "PREPARING",
      },
    ],
    ...extra,
  });
}

function stock(overrides: Partial<Stock> = {}): Stock {
  return {
    ingredient_id: "i1i1i1i1-0000-0000-0000-000000000001",
    name: "TEST – Ingredient 1",
    unit: "g",
    on_hand: "10000.000",
    reserved: "500.000",
    available: "9500.000",
    low_stock_threshold: null,
    is_low: false,
    is_test_fixture: true,
    used_in: ["TEST – Synthetic Dish A"],
    updated_at: "2026-11-12T10:00:00Z",
    ...overrides,
  };
}

function settings(overrides: Partial<KitchenSettings> = {}): KitchenSettings {
  return {
    kitchen_id: KITCHEN,
    kitchen_name: "TEST – Chennai Kitchen",
    mode: "NORMAL",
    normal_capacity: { value: 10, is_test_default: true },
    busy_capacity: { value: 5, is_test_default: true },
    acceptance_timeout_minutes: { value: 5, is_test_default: true },
    intake: { mode: "NORMAL", capacity: 10, active_orders: 0, accepting: true, refusal: null },
    can_change: true,
    ...overrides,
  };
}

function request(overrides: Partial<AvailabilityRequest> = {}): AvailabilityRequest {
  return {
    id: "r1r1r1r1-0000-0000-0000-000000000001",
    menu_item_id: "m3",
    dish_name: "TEST – Synthetic Dish C",
    publication_status: "PUBLISHED",
    is_test_fixture: true,
    kitchen_id: KITCHEN,
    region_id: "r1",
    kind: "MAKE_UNAVAILABLE",
    reason: "Ingredient 5 spoiled",
    status: "PENDING",
    requested_by_name: "Demo Kitchen Staff",
    requested_role: "KITCHEN_STAFF",
    requested_at: "2026-11-12T10:00:00Z",
    decided_by_name: null,
    decided_role: null,
    decided_at: null,
    decision_reason: null,
    ...overrides,
  };
}

describe("live orders (KI-01–KI-03)", () => {
  it("shows incoming orders with warnings and accepts in one tap", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () => json(queue({ incoming: [order({ overdue: true })] })),
      "POST /api/v1/kitchen/orders/0a0a0a0a-0000-0000-0000-000000000001/accept": () =>
        json(held("0a0a0a0a-0000-0000-0000-000000000001", "ACCEPTED", "Accepted")),
    });
    renderAt("/kitchen/live-orders");
    const card = await screen.findByRole("article", { name: "Order 0a0a0a0a" });
    expect(within(card).getByText(/Overdue · waiting \d+ min/)).toBeInTheDocument();
    expect(within(card).getByText("Test order")).toBeInTheDocument();
    expect(within(card).getByText("Instructions: Less oil")).toBeInTheDocument();
    expect(screen.getByText(/test default, not\s+final/)).toBeInTheDocument();
    expect(screen.getByTestId("poll-note")).toHaveTextContent("Live updates paused · updates every 10 s");
    expect(screen.getByTestId("intake")).toHaveTextContent("2 / 10 orders in progress");
    await userEvent.click(within(card).getByRole("button", { name: "Accept" }));
    await waitFor(() =>
      expect(api.calls.some((r) => r.method === "POST" && r.url.endsWith("/accept"))).toBe(true),
    );
  });

  it("explains a stock shortage with the short ingredient", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () => json(queue({ incoming: [order()] })),
      "POST /api/v1/kitchen/orders/0a0a0a0a-0000-0000-0000-000000000001/accept": () =>
        json(
          {
            code: "stock_short",
            message: "Not enough stock to accept this order",
            shortages: [
              { ingredient: "TEST – Ingredient 3", unit: "g", needed: "300.000", available: "100.000" },
            ],
          },
          409,
        ),
    });
    renderAt("/kitchen/live-orders");
    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Not enough stock to accept this order. TEST – Ingredient 3: needs 300 g, 100 g available.",
    );
  });

  it("explains a Paused refusal", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () => json(queue({ incoming: [order()] })),
      "POST /api/v1/kitchen/orders/0a0a0a0a-0000-0000-0000-000000000001/accept": () =>
        json({ code: "kitchen_paused", message: "paused" }, 409),
    });
    renderAt("/kitchen/live-orders");
    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The kitchen is Paused");
  });

  it("rejects with a reason", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () => json(queue({ incoming: [order()] })),
      "POST /api/v1/kitchen/orders/0a0a0a0a-0000-0000-0000-000000000001/reject": () =>
        json(order({ fulfilment_status: "REJECTED", status_label: "Rejected" })),
    });
    renderAt("/kitchen/live-orders");
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.type(screen.getByLabelText("Why is this order rejected?"), "Out of packaging");
    await userEvent.click(screen.getByRole("button", { name: "Reject order" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/reject"))).toBe(true));
    const post = api.calls.find((r) => r.url.endsWith("/reject"));
    expect(await post?.json()).toEqual({ reason: "Out of packaging" });
  });

  it("lists held orders first accepted first, with the agent line", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () =>
        json(
          queue({
            held: [
              held("bbbbbbbb-0000-0000-0000-000000000001", "PREPARING", "Preparing", {
                assignment: { status: "OFFERED", agent_name: "Demo Delivery Agent" },
              }),
              held("cccccccc-0000-0000-0000-000000000001", "ACCEPTED", "Accepted"),
            ],
          }),
        ),
    });
    renderAt("/kitchen/live-orders");
    const list = await screen.findByRole("list", { name: "Accepted orders in FIFO order" });
    const names = within(list)
      .getAllByRole("heading")
      .map((h) => h.textContent);
    expect(names).toEqual(["Order bbbbbbbb", "Order cccccccc"]);
    expect(within(list).getByText("Offered to Demo Delivery Agent")).toBeInTheDocument();
    expect(within(list).getByText("Awaiting agent")).toBeInTheDocument();
    expect(screen.getByText(/simulated until Task 9/)).toBeInTheDocument();
  });

  it("shows the empty and error states", async () => {
    mockApi({ "GET /api/v1/me": () => json(KS), "GET /api/v1/kitchen/orders": () => json(queue()) });
    renderAt("/kitchen/live-orders");
    expect(await screen.findByText("No incoming orders")).toBeInTheDocument();
  });

  it("denies accounts without kitchen.orders.view", async () => {
    mockApi({ "GET /api/v1/me": () => json({ ...KS, permissions: [] }) });
    renderAt("/kitchen/live-orders");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });
});

describe("preparation board (KI-04–KI-06)", () => {
  it("starts an order and steps items; Cannot fulfil only with the permission", async () => {
    const id = "bbbbbbbb-0000-0000-0000-000000000001";
    const api = mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () => json(queue({ held: [held(id, "ACCEPTED", "Accepted")] })),
      [`POST /api/v1/kitchen/orders/${id}/start`]: () => json(held(id, "PREPARING", "Preparing")),
      [`POST /api/v1/kitchen/orders/${id}/items/1a1a1a1a-0000-0000-0000-000000000001/status`]: () =>
        json(held(id, "PREPARING", "Preparing")),
    });
    renderAt("/kitchen/preparation");
    const card = await screen.findByRole("article", { name: "Order bbbbbbbb" });
    expect(within(card).getByText(/recipe v1/)).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Cannot fulfil" })).not.toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Start order" }));
    await userEvent.click(
      within(card).getByRole("button", { name: "Mark TEST – Synthetic Dish A Preparing" }),
    );
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/status"))).toBe(true));
    const step = api.calls.find((r) => r.url.endsWith("/status"));
    expect(await step?.json()).toEqual({ status: "PREPARING" });
    expect(screen.getByRole("heading", { name: "Accepted (1)" })).toBeInTheDocument();
  });

  it("offers Cannot fulfil to the Kitchen Manager with a reason", async () => {
    const id = "bbbbbbbb-0000-0000-0000-000000000001";
    const api = mockApi({
      "GET /api/v1/me": () => json(KM),
      "GET /api/v1/kitchen/orders": () =>
        json(queue({ can_reject_accepted: true, held: [held(id, "PREPARING", "Preparing")] })),
      [`POST /api/v1/kitchen/orders/${id}/reject`]: () => json(held(id, "REJECTED", "Rejected")),
    });
    renderAt("/kitchen/preparation");
    await userEvent.click(await screen.findByRole("button", { name: "Cannot fulfil" }));
    await userEvent.type(screen.getByLabelText("Why can this order not be fulfilled?"), "Burner failed");
    await userEvent.click(screen.getByRole("button", { name: "Reject order" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/reject"))).toBe(true));
  });
});

describe("inventory (KI-21–KI-24)", () => {
  const dishes = [
    { id: "m3", name: "TEST – Synthetic Dish C", publication_status: "PUBLISHED", is_test_fixture: true },
  ];
  const common = {
    "GET /api/v1/kitchen/orders": () => json(queue()),
    "GET /api/v1/menu/availability/dishes": () => json(dishes),
    "GET /api/v1/menu/availability/requests": () => json([]),
  };

  it("gives the Kitchen Manager full stock with the Test stock badge and a reasoned adjustment", async () => {
    const api = mockApi({
      ...common,
      "GET /api/v1/me": () => json(KM),
      "GET /api/v1/kitchen/inventory": () => json([stock()]),
      "POST /api/v1/kitchen/inventory/i1i1i1i1-0000-0000-0000-000000000001/adjust": () =>
        json(stock({ on_hand: "9900.000" })),
    });
    renderAt("/kitchen/inventory");
    const row = await screen.findByTestId("stock-row");
    expect(within(row).getByText("Test stock")).toBeInTheDocument();
    expect(within(row).getByText("9,500 g")).toBeInTheDocument();
    expect(within(row).getByText("Not set")).toBeInTheDocument();
    expect(within(row).getByText(/Used in: TEST – Synthetic Dish A/)).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Adjust stock of TEST – Ingredient 1" }));
    await userEvent.type(within(row).getByLabelText("Change in g"), "-100");
    await userEvent.type(within(row).getByLabelText("Reason for the adjustment"), "Spilled");
    await userEvent.click(within(row).getByRole("button", { name: "Save adjustment" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/adjust"))).toBe(true));
    const post = api.calls.find((r) => r.url.endsWith("/adjust"));
    expect(await post?.json()).toEqual({ delta: "-100", reason: "Spilled" });
  });

  it("shows Kitchen Staff low-stock alerts only and lets them request unavailability", async () => {
    const api = mockApi({
      ...common,
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/inventory/low-stock": () =>
        json([stock({ is_low: true, low_stock_threshold: "9500.000" })]),
      "POST /api/v1/menu/availability/requests": () => json(request(), 201),
    });
    renderAt("/kitchen/inventory");
    expect(await screen.findByRole("heading", { name: "Low-stock alerts (1)" })).toBeInTheDocument();
    expect(api.calls.some((r) => new URL(r.url).pathname === "/api/v1/kitchen/inventory")).toBe(false);
    await userEvent.click(await screen.findByRole("button", { name: "Request unavailable" }));
    await userEvent.type(
      screen.getByLabelText(/Why should TEST – Synthetic Dish C come off the menu/),
      "Ingredient 5 spoiled",
    );
    await userEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Request sent for TEST – Synthetic Dish C.")).toBeInTheDocument();
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({
      menu_item_id: "m3",
      kind: "MAKE_UNAVAILABLE",
      reason: "Ingredient 5 spoiled",
    });
  });
});

describe("settings (KI-12–KI-15)", () => {
  it("labels test defaults and saves a mode change with a reason", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(KM),
      "GET /api/v1/kitchen/settings": () => json(settings()),
      "PUT /api/v1/kitchen/settings": () => json(settings({ mode: "PAUSED" })),
    });
    renderAt("/kitchen/settings");
    expect(await screen.findAllByText("Test default, not a final value (DDR-42 open)")).toHaveLength(2);
    await userEvent.click(screen.getByRole("radio", { name: /Paused/ }));
    await userEvent.click(screen.getByRole("button", { name: "Review and save" }));
    await userEvent.type(
      screen.getByLabelText("Why are you changing the kitchen settings?"),
      "Equipment check",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(api.calls.some((r) => r.method === "PUT")).toBe(true));
    const put = api.calls.find((r) => r.method === "PUT");
    expect(await put?.json()).toEqual({
      mode: "PAUSED",
      normal_capacity: 10,
      busy_capacity: 5,
      reason: "Equipment check",
    });
  });

  it("refuses a Busy capacity above the normal one before asking for a reason", async () => {
    mockApi({ "GET /api/v1/me": () => json(KM), "GET /api/v1/kitchen/settings": () => json(settings()) });
    renderAt("/kitchen/settings");
    const busy = await screen.findByLabelText("Busy capacity (orders)");
    await userEvent.clear(busy);
    await userEvent.type(busy, "12");
    await userEvent.click(screen.getByRole("button", { name: "Review and save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Busy capacity cannot be higher than normal capacity.",
    );
  });

  it("is denied to Kitchen Staff", async () => {
    mockApi({ "GET /api/v1/me": () => json(KS) });
    renderAt("/kitchen/settings");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });
});

describe("exceptions and overview", () => {
  it("lists overdue incoming orders and low stock", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () =>
        json(
          queue({
            incoming: [order({ overdue: true }), order({ id: "dddddddd-0000-0000-0000-000000000001" })],
          }),
        ),
      "GET /api/v1/kitchen/inventory/low-stock": () =>
        json([stock({ is_low: true, low_stock_threshold: "9500.000" })]),
    });
    renderAt("/kitchen/exceptions");
    expect(await screen.findByRole("heading", { name: "Overdue incoming orders (1)" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Low stock (1)" })).toBeInTheDocument();
  });

  it("summarises the kitchen", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () =>
        json(
          queue({
            incoming: [order()],
            held: [held("bbbbbbbb-0000-0000-0000-000000000001", "PREPARING", "Preparing")],
          }),
        ),
      "GET /api/v1/kitchen/inventory/low-stock": () => json([]),
    });
    renderAt("/kitchen");
    const summary = await screen.findByRole("list", { name: "Kitchen summary" });
    expect(within(summary).getByRole("link", { name: /1\s*Incoming/ })).toHaveAttribute(
      "href",
      "/kitchen/live-orders",
    );
    expect(within(summary).getByRole("link", { name: /1\s*Preparing/ })).toBeInTheDocument();
  });

  it("shows an error state when the queue cannot load", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/kitchen/orders": () => json({ code: "http_500" }, 500),
      "GET /api/v1/kitchen/inventory/low-stock": () => json([]),
    });
    renderAt("/kitchen");
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
  });
});

describe("management dish availability (KI-24)", () => {
  it("approves a pending request and rejects another with a reason", async () => {
    const other = request({
      id: "r2r2r2r2-0000-0000-0000-000000000001",
      dish_name: "TEST – Synthetic Dish B",
    });
    const api = mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/menu/availability/requests": () => json([request(), other]),
      "POST /api/v1/menu/availability/requests/r1r1r1r1-0000-0000-0000-000000000001/decision": () =>
        json(request({ status: "APPROVED", publication_status: "TEMPORARILY_UNAVAILABLE" })),
      "POST /api/v1/menu/availability/requests/r2r2r2r2-0000-0000-0000-000000000001/decision": () =>
        json(request({ status: "REJECTED" })),
    });
    renderAt("/management/dish-availability");
    const [first, second] = await screen.findAllByTestId("availability-request");
    if (!first || !second) throw new Error("two requests expected");
    await userEvent.click(within(first).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(api.calls.filter((r) => r.method === "POST")).toHaveLength(1));
    await userEvent.click(within(second).getByRole("button", { name: "Reject" }));
    await userEvent.type(
      screen.getByLabelText(/Why is the request for TEST – Synthetic Dish B rejected/),
      "Check quality",
    );
    await userEvent.click(screen.getByRole("button", { name: "Reject request" }));
    await waitFor(() => expect(api.calls.filter((r) => r.method === "POST")).toHaveLength(2));
    const bodies = await Promise.all(api.calls.filter((r) => r.method === "POST").map((r) => r.json()));
    expect(bodies).toEqual([
      { approve: true, reason: null },
      { approve: false, reason: "Check quality" },
    ]);
  });

  it("is denied without the approval permission", async () => {
    mockApi({ "GET /api/v1/me": () => json({ ...RM, permissions: ["management.operations.view"] }) });
    renderAt("/management/dish-availability");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });
});
