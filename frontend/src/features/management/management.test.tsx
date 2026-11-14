import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Agent, Inventory, OrderDetail, OrderPage, OrderRow, Overview, Refunds, Staff } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

// Fixtures mirror the generated schema; values are TEST data (DDR-114).
const REGION = "r0r0r0r0-0000-0000-0000-000000000001";
const KITCHEN = "k0k0k0k0-0000-0000-0000-000000000001";
const ORDER = "0d0d0d0d-0000-0000-0000-000000000001";
const SHARED = [
  "management.operations.view",
  "management.inventory.view",
  "management.staff.manage",
  "management.agents.assign",
  "kitchen.orders.reject_accepted",
  "management.audit.regional",
  "menu.publish",
];
const RM = me({
  user_id: "00000000-0000-0000-0000-0000000000a1",
  display_name: "Demo Regional Manager",
  roles: [{ role: "REGIONAL_MANAGER", region_id: REGION, kitchen_id: null }],
  permissions: SHARED,
  portals: ["management"],
});
const CA = me({
  user_id: "00000000-0000-0000-0000-0000000000c1",
  display_name: "Demo Central Administrator",
  roles: [{ role: "CENTRAL_ADMIN", region_id: null, kitchen_id: null }],
  permissions: [
    ...SHARED,
    "management.regional_managers.manage",
    "management.audit.global",
    "management.settings.global",
  ],
  portals: ["management"],
});

const KITCHENS = [
  {
    id: KITCHEN,
    code: "KIT-CHN-001",
    name: "Chennai Kitchen",
    region_id: REGION,
    region_name: "Chennai",
    mode: "NORMAL",
    intake: { mode: "NORMAL", capacity: 10, active_orders: 2, accepting: true, refusal: null },
  },
];
const REGIONS = [{ id: REGION, code: "REG-CHN-001", name: "Chennai" }];

function row(overrides: Partial<OrderRow> = {}): OrderRow {
  return {
    id: ORDER,
    placed_at: "2026-11-12T10:00:00Z",
    fulfilment_status: "OUT_FOR_DELIVERY",
    status_label: "Out for delivery",
    is_test_fixture: true,
    kitchen_name: "Chennai Kitchen",
    payable_paise: 25000,
    payment_method: "COD",
    payment_status: "COLLECTION_PENDING",
    agent_name: "TEST – Agent",
    assignment_status: "ACCEPTED",
    delivery_exception_open: false,
    ...overrides,
  };
}

function detail(order: Partial<OrderRow> = {}): OrderDetail {
  return {
    order: row(order),
    items: [{ name: "TEST – Synthetic Dish A", quantity: 2 }],
    timeline: [
      {
        machine: "fulfilment",
        from_status: "READY_FOR_PICKUP",
        to_status: "PICKED_UP",
        actor_role: "DELIVERY_AGENT",
        actor_name: "TEST – Agent",
        reason: null,
        changed_at: "2026-11-12T10:20:00Z",
      },
    ],
  };
}

describe("management overview", () => {
  it("shows persisted counts and states that KPIs wait for Task 13", async () => {
    const overview: Overview = {
      orders_by_status: { PENDING_KITCHEN: 3, OUT_FOR_DELIVERY: 1 },
      overdue_incoming: 1,
      availability_requests: 2,
      failure_requests: 0,
      delivery_exceptions: 1,
      online_agents: 4,
      active_deliveries: 1,
      kitchens: KITCHENS,
      kpis_available: false,
    };
    mockApi({ "GET /api/v1/me": () => json(RM), "GET /api/v1/management/overview": () => json(overview) });
    renderAt("/management");
    expect(await screen.findByTestId("count-PENDING_KITCHEN")).toHaveTextContent("3");
    expect(screen.getByTestId("count-ACCEPTED")).toHaveTextContent("0");
    expect(screen.getByRole("link", { name: /Overdue incoming orders/ })).toHaveTextContent("1");
    expect(screen.getByRole("table", { name: "Kitchens" })).toHaveTextContent("2 of 10 active");
    expect(screen.getByTestId("kpi-note")).toHaveTextContent("Task 13");
    expect(screen.queryByText(/revenue ₹/i)).not.toBeInTheDocument();
  });
});

describe("orders and exceptions", () => {
  it("sends the chosen filters and exports the same view as CSV", async () => {
    const page: OrderPage = { rows: [row()], total: 1, page: 1, page_size: 50 };
    const { calls } = mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/management/orders": () => json(page),
      "GET /api/v1/management/kitchens": () => json(KITCHENS),
      "GET /api/v1/delivery/manage/agents": () => json([]),
    });
    renderAt("/management/orders?exception=true");
    expect(await screen.findByRole("table", { name: "Orders" })).toHaveTextContent("Test order");
    expect(screen.getByLabelText("Exception open only")).toBeChecked();

    await userEvent.selectOptions(screen.getByLabelText("Status"), "OUT_FOR_DELIVERY");
    await userEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => {
      const last = calls.filter((c) => c.url.includes("/management/orders")).at(-1);
      expect(last?.url).toContain("status=OUT_FOR_DELIVERY");
      expect(last?.url).toContain("exception=true");
    });
    const csv = screen.getByRole("link", { name: "Export CSV" });
    expect(csv.getAttribute("href")).toBe(
      "/api/v1/management/orders.csv?status=OUT_FOR_DELIVERY&exception=true",
    );
  });

  it("shows the backend's reason when a filter is refused", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/management/orders": () =>
        json({ code: "http_422", message: "Choose a range of at most 31 days" }, 422),
      "GET /api/v1/management/kitchens": () => json(KITCHENS),
      "GET /api/v1/delivery/manage/agents": () => json([]),
    });
    renderAt("/management/orders");
    expect(await screen.findByText("Choose a range of at most 31 days")).toBeInTheDocument();
  });
});

describe("order detail", () => {
  it("decides an open failure request only with a reason", async () => {
    const { calls } = mockApi({
      "GET /api/v1/me": () => json(RM),
      [`GET /api/v1/management/orders/${ORDER}`]: () =>
        json(detail({ assignment_status: "FAILURE_REQUESTED" })),
      [`POST /api/v1/delivery/manage/orders/${ORDER}/failure-decision`]: () => json({}),
    });
    renderAt(`/management/orders/${ORDER}`);
    expect(await screen.findByRole("table", { name: "Timeline" })).toHaveTextContent("Picked up");
    expect(screen.queryByRole("button", { name: "Assign agent" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Return to agent" }));
    await userEvent.click(screen.getByRole("button", { name: "Return to agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 3 characters");
    expect(calls.some((c) => c.method === "POST")).toBe(false);

    await userEvent.type(screen.getByLabelText(/continue the delivery/), "Customer is reachable now");
    await userEvent.click(screen.getByRole("button", { name: "Return to agent" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST");
    expect(await post?.json()).toEqual({ approve: false, reason: "Customer is reachable now" });
  });

  it("labels a failed delivery's refund as pending with exceptional refunds disabled", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      [`GET /api/v1/management/orders/${ORDER}`]: () =>
        json(
          detail({
            fulfilment_status: "DELIVERY_FAILED",
            status_label: "Delivery failed",
            assignment_status: null,
          }),
        ),
    });
    renderAt(`/management/orders/${ORDER}`);
    expect(await screen.findByTestId("refund-pending")).toHaveTextContent("DDR-44");
    expect(screen.queryByRole("heading", { name: "Actions" })).not.toBeInTheDocument();
  });

  it("offers assignment to free online agents while the kitchen holds the order", async () => {
    const agents: Agent[] = [
      {
        id: "a1",
        name: "Online Agent",
        availability: "ONLINE",
        availability_changed_at: null,
        live_status: null,
        live_order_id: null,
      },
      {
        id: "a2",
        name: "Busy Agent",
        availability: "ONLINE",
        availability_changed_at: null,
        live_status: "ACCEPTED",
        live_order_id: "x",
      },
      {
        id: "a3",
        name: "Offline Agent",
        availability: "OFFLINE",
        availability_changed_at: null,
        live_status: null,
        live_order_id: null,
      },
    ];
    mockApi({
      "GET /api/v1/me": () => json(RM),
      [`GET /api/v1/management/orders/${ORDER}`]: () =>
        json(
          detail({
            fulfilment_status: "PREPARING",
            status_label: "Preparing",
            agent_name: null,
            assignment_status: null,
          }),
        ),
      "GET /api/v1/delivery/manage/agents": () => json(agents),
    });
    renderAt(`/management/orders/${ORDER}`);
    const select = await screen.findByLabelText("Assign to");
    expect(
      within(select)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Online Agent"]);
    expect(screen.getByRole("button", { name: "Cannot fulfil" })).toBeInTheDocument();
  });
});

const STAFF: Staff[] = [
  {
    assignment_id: "g1",
    user_id: RM.user_id,
    display_name: "Demo Regional Manager",
    mobile_masked: "+91*******05",
    user_status: "ACTIVE",
    role: "REGIONAL_MANAGER",
    region_id: REGION,
    kitchen_id: null,
    granted_at: "2026-11-01T00:00:00Z",
  },
  {
    assignment_id: "g2",
    user_id: "u-ks",
    display_name: "Demo Kitchen Staff",
    mobile_masked: "+91*******03",
    user_status: "ACTIVE",
    role: "KITCHEN_STAFF",
    region_id: REGION,
    kitchen_id: KITCHEN,
    granted_at: "2026-11-01T00:00:00Z",
  },
];

function staffApi(who: typeof RM, extra: Record<string, (r: Request) => Response> = {}) {
  return mockApi({
    "GET /api/v1/me": () => json(who),
    "GET /api/v1/management/staff": () => json(STAFF),
    "GET /api/v1/management/regions": () => json(REGIONS),
    "GET /api/v1/management/kitchens": () => json(KITCHENS),
    ...extra,
  });
}

describe("staff and access", () => {
  it("lets an RM grant only kitchen and agent roles and never change their own access", async () => {
    staffApi(RM);
    renderAt("/management/staff");
    const role = await screen.findByLabelText("Role");
    expect(
      within(role)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Kitchen Staff", "Kitchen Manager", "Delivery Agent"]);
    const self = await screen.findByRole("list", { name: "Roles of Demo Regional Manager" });
    expect(within(self).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Deactivate" })).toHaveLength(1);
  });

  it("lets a CA grant the Regional Manager role", async () => {
    staffApi(CA);
    renderAt("/management/global-staff");
    const role = await screen.findByLabelText("Role");
    expect(
      within(role)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toContain("Regional Manager");
  });

  it("adds a kitchen role with the kitchen and the reason", async () => {
    const { calls } = staffApi(RM, {
      "POST /api/v1/management/staff": () => json({ ...STAFF[1], display_name: "New Cook" }, 201),
    });
    renderAt("/management/staff");
    await userEvent.type(await screen.findByLabelText("Name"), "New Cook");
    await userEvent.type(screen.getByLabelText("Mobile number"), "+91-00000-12345");
    await userEvent.type(screen.getByLabelText("Reason"), "Joining the morning shift");
    await userEvent.click(screen.getByRole("button", { name: "Add role" }));
    expect(await screen.findByRole("status")).toHaveTextContent("New Cook added as Kitchen Staff");
    const post = calls.find((c) => c.method === "POST");
    expect(await post?.json()).toEqual({
      display_name: "New Cook",
      mobile: "+91-00000-12345",
      role: "KITCHEN_STAFF",
      region_id: REGION,
      kitchen_id: KITCHEN,
      reason: "Joining the morning shift",
    });
  });

  it("shows the backend refusal when a deactivation is blocked by active work", async () => {
    staffApi(RM, {
      "PUT /api/v1/management/staff/u-ks/status": () =>
        json(
          { code: "http_409", message: "The agent has an active delivery; reassign or resolve it first" },
          409,
        ),
    });
    renderAt("/management/staff");
    await userEvent.click(await screen.findByRole("button", { name: "Deactivate" }));
    await userEvent.type(screen.getByLabelText(/Why are you deactivating/), "Left the company");
    await userEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("active delivery");
  });
});

describe("payments, inventory and placeholders", () => {
  it("shows refunds read-only with exceptional refunds disabled (DDR-44)", async () => {
    const refunds: Refunds = {
      rows: [
        {
          order_id: ORDER,
          is_test_fixture: true,
          amount_paise: 25000,
          method: "UPI",
          status: "REFUNDED",
          reason: "Kitchen rejected",
          actor_role: "KITCHEN_MANAGER",
          actor_name: "Demo Kitchen Manager",
          changed_at: "2026-11-12T11:00:00Z",
          pending_decision: false,
        },
      ],
      exceptional_refunds_enabled: false,
      disabled_reason: "Disabled: no threshold configured (DDR-44)",
    };
    mockApi({ "GET /api/v1/me": () => json(RM), "GET /api/v1/management/refunds": () => json(refunds) });
    renderAt("/management/payments");
    expect(await screen.findByTestId("refund-rules")).toHaveTextContent(
      "Disabled: no threshold configured (DDR-44)",
    );
    expect(screen.getByRole("table", { name: "Refunds" })).toHaveTextContent("Kitchen rejected");
    expect(screen.queryByRole("button", { name: /refund/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Promotions" }).closest("section")).toHaveTextContent(
      "Not built yet",
    );
  });

  it("shows stock read-only with the Test stock label", async () => {
    const inventory: Inventory = {
      kitchen_id: KITCHEN,
      stock: [
        {
          ingredient_id: "i1",
          name: "TEST – Ingredient 1",
          unit: "g",
          on_hand: "10000.000",
          reserved: "200.000",
          available: "9800.000",
          low_stock_threshold: null,
          is_test_fixture: true,
        },
      ],
      movements: [],
    };
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/management/kitchens": () => json(KITCHENS),
      [`GET /api/v1/management/kitchens/${KITCHEN}/inventory`]: () => json(inventory),
    });
    renderAt("/management/menu");
    const table = await screen.findByRole("table", { name: "Stock" });
    expect(table).toHaveTextContent("9800 g");
    expect(table).toHaveTextContent("Not set");
    expect(screen.getByTestId("test-badge")).toHaveTextContent("Test stock");
    expect(screen.queryByRole("button", { name: /adjust/i })).not.toBeInTheDocument();
  });

  it("explains why YAML configuration is not built", async () => {
    mockApi({ "GET /api/v1/me": () => json(CA) });
    renderAt("/management/yaml");
    const page = await screen.findByRole("heading", { name: "YAML Configuration Management" });
    expect(page.closest("section")).toHaveTextContent("DDR-44, class B");
  });
});
