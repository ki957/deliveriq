import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { json, me, mockApi, renderAt } from "@/test/render";

import { visibleNav } from "./portal-shell";
import { managementConfig } from "@/portals/management/config";

const KITCHEN_MANAGER = me({
  display_name: "Demo Kitchen Manager",
  roles: [{ role: "KITCHEN_MANAGER", region_id: "r1", kitchen_id: "k1" }],
  permissions: ["kitchen.mode.change", "kitchen.orders.view"],
  portals: ["kitchen"],
});

describe("route guards", () => {
  it("sends a visitor without a session to the portal login", async () => {
    mockApi({
      "GET /api/v1/me": () => json({ code: "http_401" }, 401),
      "POST /api/v1/auth/trusted-login": () => json({ detail: "x" }, 401),
    });
    const router = renderAt("/management/reports");
    await waitFor(() => expect(router.state.location.pathname).toBe("/management/login"));
    expect(router.state.location.search).toBe("?next=%2Fmanagement%2Freports");
  });

  it("shows a denied state when the account has no role for the portal", async () => {
    mockApi({ "GET /api/v1/me": () => json(me()) });
    renderAt("/kitchen");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });

  it("lets anyone browse the customer portal but guards account pages", async () => {
    mockApi({
      "GET /api/v1/me": () => json({ code: "http_401" }, 401),
      "POST /api/v1/auth/trusted-login": () => json({ detail: "x" }, 401),
    });
    const router = renderAt("/customer");
    expect(await screen.findByRole("heading", { name: "Welcome to DeliverIQ" })).toBeInTheDocument();
    router.navigate("/customer/orders");
    await waitFor(() => expect(router.state.location.pathname).toBe("/customer/login"));
  });
});

describe("portal shell", () => {
  it("renders a labelled placeholder, the placeholder logo and the user's role", async () => {
    // Task 8B built every Kitchen screen; Management → Kitchen Operations is still Task 10.
    const admin = me({
      display_name: "Demo Central Administrator",
      roles: [{ role: "CENTRAL_ADMIN", region_id: null, kitchen_id: null }],
      permissions: ["management.operations.view"],
      portals: ["management"],
    });
    mockApi({ "GET /api/v1/me": () => json(admin) });
    renderAt("/management/kitchen");
    const page = await screen.findByRole("heading", { name: "Kitchen Operations" });
    expect(page.closest("section")).toHaveTextContent("Not built yet");
    expect(page.closest("section")).toHaveTextContent("Task 10");
    expect(screen.getAllByText("Placeholder logo").length).toBeGreaterThan(0);
    expect(screen.getByTestId("account-roles")).toHaveTextContent("Central Administrator");
  });

  it("shows Kitchen Settings only to roles with the permission", async () => {
    // Kitchen Staff permissions: no mode change; recipes are visible to both kitchen roles.
    mockApi({
      "GET /api/v1/me": () =>
        json({ ...KITCHEN_MANAGER, permissions: ["kitchen.orders.view", "kitchen.recipes.view"] }),
    });
    renderAt("/kitchen");
    const [nav] = await screen.findAllByRole("navigation", { name: "Kitchen navigation" });
    if (!nav) throw new Error("navigation not rendered");
    expect(within(nav).queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Recipes" })).toBeInTheDocument();
  });
});

describe("management navigation is permission-derived (MG-10)", () => {
  const labels = (permissions: string[]) =>
    visibleNav(managementConfig.nav, (p) => permissions.includes(p)).map((i) => i.label);
  const shared = ["management.staff.manage", "management.settings.regional", "management.audit.regional"];

  it("gives a Regional Manager the regional sections only", () => {
    const rm = labels(shared);
    expect(rm).toContain("Staff & Access");
    expect(rm).not.toContain("Global Configuration");
    expect(rm).not.toContain("Global Staff & Regional Manager Access");
  });

  it("gives a Central Administrator the global sections instead of regional staff", () => {
    const ca = labels([
      ...shared,
      "management.regional_managers.manage",
      "management.settings.global",
      "management.audit.global",
    ]);
    expect(ca).toContain("Global Staff & Regional Manager Access");
    expect(ca).toContain("YAML Configuration Management");
    expect(ca).not.toContain("Staff & Access");
  });

  it("does not show later AI features yet", () => {
    const all = managementConfig.nav.map((i) => i.label);
    expect(all).not.toContain("Management AI Copilot");
    expect(all).not.toContain("AI Model Configuration");
  });
});

describe("lost-mobile recovery (DDR-41)", () => {
  it("has no route", async () => {
    mockApi({ "GET /api/v1/me": () => json({ code: "http_401" }, 401) });
    renderAt("/customer/recover");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
