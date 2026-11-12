import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { MenuItem, RecipeDetail, RecipeVersion } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

const CA = me({
  roles: [{ role: "CENTRAL_ADMIN", region_id: null, kitchen_id: null }],
  permissions: ["menu.publish", "recipes.signoff.product_owner", "pipelines.view"],
  portals: ["management"],
});
const RM = me({
  roles: [{ role: "REGIONAL_MANAGER", region_id: "r1", kitchen_id: null }],
  permissions: ["menu.publish", "pipelines.view"],
  portals: ["management"],
});

function item(overrides: Partial<MenuItem> = {}): MenuItem {
  return {
    id: "dddddddd-0000-0000-0000-000000000001",
    name: "TEST – Synthetic Dish D",
    description: "TEST – synthetic dish for workflow testing",
    price_paise: 44400,
    is_veg: true,
    spice_level: "TEST",
    prep_time_minutes: 10,
    image_url: null,
    image_is_placeholder: true,
    category: "TEST – Category",
    is_test_fixture: true,
    tax_classification: "TEST",
    publication_status: "DRAFT",
    kitchen_id: "k1",
    region_id: "r1",
    recipe_id: "r-1",
    has_active_recipe: false,
    updated_at: "2026-11-12T10:00:00Z",
    ...overrides,
  };
}

describe("menu publication", () => {
  it("offers the next step only and shows the readiness refusal from the backend", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/menu/manage/items": () =>
        json([
          item(),
          item({
            id: "e1",
            name: "TEST – Synthetic Dish A",
            publication_status: "PUBLISHED",
            price_paise: 11100,
            has_active_recipe: true,
          }),
        ]),
      "POST /api/v1/menu/manage/items/dddddddd-0000-0000-0000-000000000001/transitions": () =>
        json({ code: "http_409", message: "menu item x is not ready: missing active recipe version" }, 409),
    });
    renderAt("/management/menu-publication");
    expect(await screen.findByText("₹444 · TEST – Category · recipe not active")).toBeInTheDocument();
    expect(screen.getAllByTestId("test-badge")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark ready for publication" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("missing active recipe version");
  });

  it("publishes a ready item", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(CA),
      "GET /api/v1/menu/manage/items": () =>
        json([item({ publication_status: "READY_FOR_PUBLICATION", has_active_recipe: true })]),
      "POST /api/v1/menu/manage/items/dddddddd-0000-0000-0000-000000000001/transitions": () =>
        json(item({ publication_status: "PUBLISHED", has_active_recipe: true })),
    });
    renderAt("/management/menu-publication");
    await userEvent.click(await screen.findByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Publish: done.")).toBeInTheDocument();
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ action: "publish" });
  });

  it("denies accounts without menu.publish", async () => {
    mockApi({ "GET /api/v1/me": () => json({ ...RM, permissions: ["pipelines.view"] }) });
    renderAt("/management/menu-publication");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });

  it("shows an empty state", async () => {
    mockApi({ "GET /api/v1/me": () => json(RM), "GET /api/v1/menu/manage/items": () => json([]) });
    renderAt("/management/menu-publication");
    expect(await screen.findByText("No menu items in your regions")).toBeInTheDocument();
  });
});

describe("recipe sign-off (product owner via a CA account)", () => {
  const pending: RecipeVersion = {
    id: "ffffffff-0000-0000-0000-000000000001",
    recipe_id: "r-9",
    name: "TEST – E2E 1",
    source_menu_id: null,
    kitchen_id: "k1",
    version: 1,
    status: "VALIDATED",
    is_test_fixture: true,
    quarantine_reason: null,
    open_review_items: 0,
    candidate_category: null,
    updated_at: "2026-11-12T10:00:00Z",
  };

  it("lists only TEST recipes in validation", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CA),
      "GET /api/v1/recipes/versions": () =>
        json([pending, { ...pending, id: "x2", name: "TEST – Synthetic Dish A", status: "ACTIVE" }]),
    });
    renderAt("/management/recipe-signoff");
    expect(await screen.findByRole("link", { name: "TEST – E2E 1" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "TEST – Synthetic Dish A" })).not.toBeInTheDocument();
  });

  it("records the product-owner sign-off with a note", async () => {
    const detail: RecipeDetail = {
      ...pending,
      prep_type: null,
      portion: null,
      method: null,
      quality: null,
      inventory_rule: null,
      validation_text: null,
      lineage: {
        source_path: null,
        source_sha256: null,
        source_card_id: null,
        source_line_start: null,
        source_line_end: null,
        source_page_ref: null,
      },
      ingredients: [],
      signoffs: [],
      missing_signoffs: ["PRODUCT_OWNER"],
      review_items: [],
    };
    const api = mockApi({
      "GET /api/v1/me": () => json(CA),
      [`GET /api/v1/recipes/versions/${pending.id}`]: () => json(detail),
      [`POST /api/v1/recipes/versions/${pending.id}/signoffs`]: () => new Response(null, { status: 204 }),
    });
    renderAt(`/management/recipe-signoff/${pending.id}`);
    await userEvent.click(await screen.findByRole("button", { name: "Record product-owner sign-off" }));
    await userEvent.type(screen.getByLabelText("Note for the product-owner sign-off"), "approved for demo");
    await userEvent.click(screen.getByRole("button", { name: "Confirm sign-off" }));
    expect(await screen.findByText("Sign-off recorded.")).toBeInTheDocument();
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ signoff_type: "PRODUCT_OWNER", note: "approved for demo" });
  });

  it("is denied to a Regional Manager", async () => {
    mockApi({ "GET /api/v1/me": () => json(RM) });
    renderAt("/management/recipe-signoff");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });
});
