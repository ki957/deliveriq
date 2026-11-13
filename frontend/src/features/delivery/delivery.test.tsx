import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MyWork, WorkOrder } from "./api";
import { BUFFER_MAX, flush, push, resetForTests, step } from "./tracker";
import { json, me, mockApi, renderAt } from "@/test/render";

const AGENT = me({
  display_name: "Demo Delivery Agent",
  roles: [{ role: "DELIVERY_AGENT", region_id: "r1", kitchen_id: null }],
  permissions: ["delivery.assignments.view"],
  portals: ["delivery"],
});
const ORDER = "0d0d0d0d-0000-0000-0000-000000000001";
const KITCHEN = { lat: 13.0827, lng: 80.2707 };
const HOME = { lat: 13.0835, lng: 80.271 };

function order(overrides: Partial<WorkOrder> = {}): WorkOrder {
  return {
    order_id: ORDER,
    items: [{ name: "TEST – Synthetic Dish A", quantity: 5 }],
    fulfilment_status: "PREPARING",
    status_label: "Go to kitchen",
    is_test_fixture: true,
    special_instructions: "Ring twice",
    delivery_address: "TEST – 1 Fixture Street",
    destination: HOME,
    kitchen_name: "TEST – Chennai Kitchen",
    kitchen: KITCHEN,
    kitchen_location_is_synthetic: true,
    customer_phone_masked: "+91********01",
    payment_method: "COD",
    payment_status: "COLLECTION_PENDING",
    payable_paise: 58500,
    customer_unavailable_since: null,
    delivery_exception_open: false,
    code_attempts_left: null,
    ...overrides,
  };
}

function work(overrides: Partial<MyWork> = {}): MyWork {
  return {
    availability: "ONLINE",
    availability_changed_at: null,
    assignment: {
      id: "a1a1a1a1-0000-0000-0000-000000000001",
      status: "ACCEPTED",
      offered_at: "2026-11-12T10:00:00Z",
      offer_seconds_left: null,
    },
    order: order(),
    customer_unavailable_wait_minutes: 5,
    gps_interval_seconds: [3, 5],
    gps_stale_seconds: 120,
    route_is_estimated: true,
    ...overrides,
  };
}

const IDLE = work({ assignment: null, order: null, availability: "OFFLINE" });

beforeEach(() => resetForTests());
afterEach(() => {
  resetForTests();
  vi.useRealTimers();
});

describe("home (DL-01, DL-04)", () => {
  it("goes online and explains how offers work", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () => json(IDLE),
      "PUT /api/v1/delivery/me/availability": () => json(work({ assignment: null, order: null })),
    });
    renderAt("/delivery");
    expect(await screen.findByText("Offline")).toBeInTheDocument();
    expect(screen.getByText("Go online to receive offers.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Go online" }));
    await waitFor(() => expect(api.calls.some((r) => r.method === "PUT")).toBe(true));
    expect(await api.calls.find((r) => r.method === "PUT")?.json()).toEqual({ online: true });
  });

  it("shows an offer with its countdown, without the address, and accepts it", async () => {
    const offer = work({
      assignment: {
        id: "a1a1a1a1-0000-0000-0000-000000000001",
        status: "OFFERED",
        offered_at: "2026-11-12T10:00:00Z",
        offer_seconds_left: 42,
      },
      order: order({ delivery_address: null, destination: null }),
    });
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () => json(offer),
      "POST /api/v1/delivery/assignments/a1a1a1a1-0000-0000-0000-000000000001/respond": () => json(work()),
    });
    renderAt("/delivery");
    const card = await screen.findByRole("region", { name: "New delivery offer" });
    expect(within(card).getByTestId("offer-countdown")).toHaveTextContent(/^4[0-2] s left to answer$/);
    expect(within(card).getByText("The address is shown after you accept.")).toBeInTheDocument();
    expect(within(card).getByText("5 × TEST – Synthetic Dish A")).toBeInTheDocument();
    expect(within(card).getByText("Test order")).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/respond"))).toBe(true));
    expect(await api.calls.find((r) => r.url.endsWith("/respond"))?.json()).toEqual({
      accept: true,
      reason: null,
    });
  });

  it("rejects an offer only with a reason", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () =>
        json(
          work({
            assignment: {
              id: "a1a1a1a1-0000-0000-0000-000000000001",
              status: "OFFERED",
              offered_at: "",
              offer_seconds_left: 30,
            },
          }),
        ),
      "POST /api/v1/delivery/assignments/a1a1a1a1-0000-0000-0000-000000000001/respond": () => json(IDLE),
    });
    renderAt("/delivery");
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await userEvent.type(screen.getByLabelText("Why are you rejecting this offer?"), "Flat tyre");
    await userEvent.click(screen.getByRole("button", { name: "Reject offer" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/respond"))).toBe(true));
    expect(await api.calls.find((r) => r.url.endsWith("/respond"))?.json()).toEqual({
      accept: false,
      reason: "Flat tyre",
    });
  });

  it("shows the next step for an accepted delivery", async () => {
    mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () =>
        json(work({ order: order({ fulfilment_status: "READY_FOR_PICKUP" }) })),
    });
    renderAt("/delivery");
    expect(await screen.findByRole("link", { name: "The order is ready: go to Pickup" })).toHaveAttribute(
      "href",
      "/delivery/pickup",
    );
    expect(screen.getByText(/Deliver to:/)).toBeInTheDocument();
  });

  it("is denied to accounts without delivery access", async () => {
    mockApi({ "GET /api/v1/me": () => json({ ...AGENT, permissions: [] }) });
    renderAt("/delivery");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });
});

describe("pickup and completion (DL-09, DL-11)", () => {
  it("blocks pickup until the order is ready", async () => {
    mockApi({ "GET /api/v1/me": () => json(AGENT), "GET /api/v1/delivery/me": () => json(work()) });
    renderAt("/delivery/pickup");
    expect(await screen.findByRole("button", { name: "Picked up" })).toBeDisabled();
    expect(screen.getByText("Wait until the kitchen marks the order Ready.")).toBeInTheDocument();
  });

  it("checks the code shape locally and shows the backend's wrong-code message", async () => {
    const away = work({ order: order({ fulfilment_status: "OUT_FOR_DELIVERY", code_attempts_left: 3 }) });
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () => json(away),
      [`POST /api/v1/delivery/orders/${ORDER}/deliver`]: () =>
        json({ code: "http_422", message: "Wrong delivery code. 2 attempt(s) left." }, 422),
    });
    renderAt("/delivery/completion");
    const input = await screen.findByLabelText("Customer's delivery code");
    await userEvent.type(input, "12a3");
    expect(input).toHaveValue("123");
    await userEvent.click(screen.getByRole("button", { name: "Confirm delivery" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter the six-digit code");
    expect(api.calls.some((r) => r.url.endsWith("/deliver"))).toBe(false);
    await userEvent.type(input, "456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm delivery" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong delivery code. 2 attempt(s) left.");
    expect(await api.calls.find((r) => r.url.endsWith("/deliver"))?.json()).toEqual({ code: "123456" });
  });

  it("locks code entry after three wrong codes and records COD collection", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () =>
        json(work({ order: order({ fulfilment_status: "OUT_FOR_DELIVERY", code_attempts_left: 0 }) })),
      [`POST /api/v1/delivery/orders/${ORDER}/cod`]: () => json({}),
    });
    renderAt("/delivery/completion");
    expect(
      await screen.findByText(/the code is locked and the manager has been alerted/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Customer's delivery code")).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Cash collected" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/cod"))).toBe(true));
    expect(await api.calls.find((r) => r.url.endsWith("/cod"))?.json()).toEqual({
      collected: true,
      reason: null,
    });
  });
});

describe("exceptions (#7 §7; DDR-14)", () => {
  it("counts down the customer-unavailable wait before contacting the manager", async () => {
    const since = new Date(Date.now() - 4 * 60_000).toISOString();
    mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () =>
        json(
          work({
            order: order({ fulfilment_status: "OUT_FOR_DELIVERY", customer_unavailable_since: since }),
          }),
        ),
    });
    renderAt("/delivery/exceptions");
    expect(await screen.findByTestId("wait-timer")).toHaveTextContent(
      /Waiting: 0:[5-6]\d left|Waiting: 1:00 left/,
    );
    expect(screen.queryByRole("button", { name: "Contact manager" })).not.toBeInTheDocument();
  });

  it("sends a refusal with its reason to the manager", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () =>
        json(work({ order: order({ fulfilment_status: "OUT_FOR_DELIVERY" }) })),
      [`POST /api/v1/delivery/orders/${ORDER}/failure-request`]: () => json({}),
    });
    renderAt("/delivery/exceptions");
    await userEvent.click(await screen.findByRole("button", { name: "Customer refused" }));
    await userEvent.type(screen.getByLabelText("Why did the customer refuse?"), "Not ordered");
    await userEvent.click(screen.getByRole("button", { name: "Send to manager" }));
    await waitFor(() => expect(api.calls.some((r) => r.url.endsWith("/failure-request"))).toBe(true));
    expect(await api.calls.find((r) => r.url.endsWith("/failure-request"))?.json()).toEqual({
      refused: true,
      reason: "Not ordered",
    });
  });
});

describe("active delivery and GPS (DL-08, DL-G2, DL-G3)", () => {
  it("reveals the number on request and never invents a position when location is denied", async () => {
    const watch = vi.fn((_ok: PositionCallback, fail: PositionErrorCallback) => {
      fail({ code: 1, PERMISSION_DENIED: 1, message: "denied" } as GeolocationPositionError);
      return 1;
    });
    Object.defineProperty(navigator, "geolocation", {
      value: { watchPosition: watch, clearWatch: vi.fn() },
      configurable: true,
    });
    mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/me": () => json(work()),
      [`GET /api/v1/delivery/orders/${ORDER}/customer-phone`]: () => json({ phone: "+919876543201" }),
    });
    renderAt("/delivery/active");
    await userEvent.click(await screen.findByRole("button", { name: "Show customer number" }));
    expect(await screen.findByRole("link", { name: "Call +919876543201" })).toHaveAttribute(
      "href",
      "tel:+919876543201",
    );
    await userEvent.click(screen.getByRole("button", { name: "Use real GPS" }));
    expect(await screen.findByText(/Location access was denied/)).toBeInTheDocument();
    expect(screen.getByText(/not shared in the background/)).toBeInTheDocument();
  });

  it("labels simulated GPS", async () => {
    mockApi({ "GET /api/v1/me": () => json(AGENT), "GET /api/v1/delivery/me": () => json(work()) });
    renderAt("/delivery/active");
    await userEvent.click(await screen.findByRole("button", { name: "Use simulated GPS" }));
    expect(await screen.findByText("Simulated GPS")).toBeInTheDocument();
    expect(screen.getByText(/15 m every 5 s/)).toBeInTheDocument();
  });

  it("shows no delivery when nothing is held", async () => {
    mockApi({ "GET /api/v1/me": () => json(AGENT), "GET /api/v1/delivery/me": () => json(IDLE) });
    renderAt("/delivery/active");
    expect(await screen.findByText("No active delivery")).toBeInTheDocument();
  });
});

describe("tracker (DDR-52, DDR-113 (8), (19))", () => {
  const point = (i: number) => ({
    lat: 13 + i / 1e5,
    lng: 80,
    accuracy_m: null,
    recorded_at: new Date(1_700_000_000_000 + i * 1000).toISOString(),
    source: "SIMULATED" as const,
  });

  it("keeps at most 300 points and drops the oldest", async () => {
    const api = mockApi({ "POST /api/v1/delivery/locations": () => json({ accepted: 100, refused: {} }) });
    for (let i = 0; i < BUFFER_MAX + 5; i++) push(point(i));
    await act(() => flush());
    const sent = (await api.calls[0]?.json()) as { points: { lat: number }[] };
    expect(sent.points).toHaveLength(100); // batches of at most 100
    expect(sent.points[0]?.lat).toBeCloseTo(13 + 5 / 1e5); // the 5 oldest were dropped
  });

  it("keeps the buffer when sending fails and re-sends later", async () => {
    let fail = true;
    const api = mockApi({
      "POST /api/v1/delivery/locations": () =>
        fail ? Promise.reject(new TypeError("network")) : json({ accepted: 1, refused: {} }),
    });
    push(point(1));
    await act(() => flush());
    fail = false;
    window.dispatchEvent(new Event("online"));
    await waitFor(() => expect(api.calls).toHaveLength(2));
  });

  it("moves a simulated position 15 m per step and stops at the destination", () => {
    const next = step(KITCHEN, HOME, 15);
    const metres = Math.hypot(
      (next.lat - KITCHEN.lat) * 111_320,
      (next.lng - KITCHEN.lng) * 111_320 * Math.cos((KITCHEN.lat * Math.PI) / 180),
    );
    expect(metres).toBeCloseTo(15, 0);
    expect(step(HOME, HOME, 15)).toEqual(HOME);
  });
});

describe("history and profile (#7 §9)", () => {
  it("lists the last 30 days with reliable durations and saves the name", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(AGENT),
      "GET /api/v1/delivery/history": () =>
        json([
          {
            order_id: ORDER,
            assignment_status: "COMPLETED",
            fulfilment_status: "DELIVERED",
            is_test_fixture: true,
            offered_at: "2026-11-12T10:00:00Z",
            picked_up_at: "2026-11-12T10:20:00Z",
            delivered_at: "2026-11-12T10:42:00Z",
            duration_minutes: 22,
          },
        ]),
      "PUT /api/v1/delivery/me/name": () => json({ display_name: "Ravi" }),
    });
    const router = renderAt("/delivery/history");
    expect(await screen.findByText(/22 min from pickup/)).toBeInTheDocument();
    await act(() => router.navigate("/delivery/profile"));
    const name = await screen.findByLabelText("Name");
    await userEvent.clear(name);
    await userEvent.type(name, "Ravi");
    await userEvent.click(screen.getByRole("button", { name: "Save name" }));
    expect(await screen.findByText("Saved as Ravi.")).toBeInTheDocument();
    expect(screen.getByText(/Profile photos are not available/)).toBeInTheDocument();
    expect(await api.calls.find((r) => r.method === "PUT")?.json()).toEqual({ display_name: "Ravi" });
  });
});
