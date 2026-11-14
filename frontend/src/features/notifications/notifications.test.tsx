import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Inbox, Notification } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

const CUSTOMER = me({ display_name: "Demo Customer" });
const ORDER = "0d0d0d0d-0000-0000-0000-000000000001";

function note(overrides: Partial<Notification> = {}): Notification {
  return {
    id: "n1",
    kind: "order.accepted",
    order_id: ORDER,
    ingredient_name: null,
    is_test_fixture: true,
    created_at: "2026-11-12T10:00:00Z",
    read_at: null,
    ...overrides,
  };
}

function inbox(rows: Notification[]): Inbox {
  return {
    rows,
    unread: rows.filter((r) => r.read_at === null).length,
    history_days: 30,
    sms: "Not configured (DDR-40)",
  };
}

describe("notifications (DDR-115 (10))", () => {
  it("words each kind, links to the order, labels test data and states the channels", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      "GET /api/v1/me/notifications": () =>
        json(
          inbox([note(), note({ id: "n2", kind: "order.agent_assigned", read_at: "2026-11-12T10:05:00Z" })]),
        ),
    });
    renderAt("/customer/notifications");
    const list = await screen.findByRole("list", { name: "Notifications" });
    const [first, second] = within(list).getAllByRole("listitem");
    expect(first).toHaveTextContent("New");
    expect(first).toHaveTextContent("The kitchen accepted your order 0d0d0d0d.");
    expect(within(first as HTMLElement).getByRole("link")).toHaveAttribute(
      "href",
      `/customer/orders/${ORDER}`,
    );
    expect(first).toHaveTextContent("Test data");
    expect(second).not.toHaveTextContent("New");
    expect(screen.getByTestId("notification-channels")).toHaveTextContent(
      "In-app only, kept for 30 days. SMS: Not configured (DDR-40).",
    );
  });

  it("shows the unread count on the header bell and marks everything read", async () => {
    let rows = [note(), note({ id: "n2", kind: "order.preparing" })];
    const { calls } = mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      "GET /api/v1/me/notifications": () => json(inbox(rows)),
      "POST /api/v1/me/notifications/read": () => {
        rows = rows.map((r) => ({ ...r, read_at: "2026-11-12T11:00:00Z" }));
        return new Response(null, { status: 204 });
      },
    });
    renderAt("/customer/notifications");
    expect(await screen.findByRole("link", { name: "Notifications, 2 unread" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Mark all as read" })).not.toBeInTheDocument(),
    );
    const post = calls.find((c) => c.method === "POST");
    expect(await post?.json()).toEqual({ ids: null });
    expect(screen.getByTestId("notifications-bell")).toHaveAccessibleName("Notifications");
  });

  it("words agent and Kitchen Manager kinds", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      "GET /api/v1/me/notifications": () =>
        json(
          inbox([
            note({ id: "a", kind: "delivery.withdrawn" }),
            note({ id: "b", kind: "delivery.failure_returned" }),
            note({ id: "c", kind: "stock.low", order_id: null, ingredient_name: "TEST – Ingredient 1" }),
          ]),
        ),
    });
    renderAt("/customer/notifications");
    const list = await screen.findByRole("list", { name: "Notifications" });
    expect(list).toHaveTextContent("Order 0d0d0d0d was withdrawn from you (reassigned or cancelled).");
    expect(list).toHaveTextContent("continue the delivery");
    expect(list).toHaveTextContent("Low stock: TEST – Ingredient 1.");
  });

  it("shows an empty history", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CUSTOMER),
      "GET /api/v1/me/notifications": () => json(inbox([])),
    });
    renderAt("/customer/notifications");
    expect(await screen.findByText("No notifications in the last 30 days")).toBeInTheDocument();
  });

  it("gives the Kitchen Manager a Notifications page and Kitchen Staff none", async () => {
    const kitchen = (permissions: string[]) =>
      me({
        roles: [{ role: "KITCHEN_STAFF", region_id: "r1", kitchen_id: "k1" }],
        permissions,
        portals: ["kitchen"],
      });
    mockApi({
      "GET /api/v1/me": () => json(kitchen(["kitchen.orders.view"])),
      "GET /api/v1/kitchen/orders": () => json({}, 500),
      "GET /api/v1/kitchen/inventory/low-stock": () => json([]),
    });
    renderAt("/kitchen");
    const [nav] = await screen.findAllByRole("navigation", { name: "Kitchen navigation" });
    expect(within(nav as HTMLElement).queryByRole("link", { name: "Notifications" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("notifications-bell")).not.toBeInTheDocument();
  });
});
