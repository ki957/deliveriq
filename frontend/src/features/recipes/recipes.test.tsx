import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { RecipeDetail, RecipeVersion, ReviewItem } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

const VID = "aaaaaaaa-0000-0000-0000-000000000001";
const KITCHEN = { region_id: "r1", kitchen_id: "k1" };
const KS = me({
  roles: [{ role: "KITCHEN_STAFF", ...KITCHEN }],
  permissions: ["kitchen.recipes.view", "kitchen.review.view"],
  portals: ["kitchen"],
});
const KM = me({
  roles: [{ role: "KITCHEN_MANAGER", ...KITCHEN }],
  permissions: [
    "kitchen.recipes.view",
    "kitchen.review.view",
    "kitchen.recipes.workflow",
    "kitchen.recipes.activate",
    "kitchen.recipes.signoff",
    "kitchen.review.acknowledge",
  ],
  portals: ["kitchen"],
});

function version(overrides: Partial<RecipeVersion> = {}): RecipeVersion {
  return {
    id: VID,
    recipe_id: "r-1",
    name: "TEST – Synthetic Dish D",
    source_menu_id: null,
    kitchen_id: "k1",
    version: 1,
    status: "DRAFT",
    is_test_fixture: true,
    quarantine_reason: null,
    open_review_items: 0,
    candidate_category: null,
    updated_at: "2026-11-12T10:00:00Z",
    ...overrides,
  };
}

function detail(overrides: Partial<RecipeDetail> = {}): RecipeDetail {
  return {
    ...version(),
    prep_type: "TEST – synthetic, not a real recipe",
    portion: "TEST – synthetic, not a real recipe",
    method: "TEST – synthetic, not a real recipe",
    quality: "TEST – synthetic, not a real recipe",
    inventory_rule: "TEST – synthetic, not a real recipe",
    validation_text: "TEST – synthetic, not a real recipe",
    lineage: {
      source_path: null,
      source_sha256: null,
      source_card_id: null,
      source_line_start: null,
      source_line_end: null,
      source_page_ref: null,
    },
    ingredients: [
      {
        line_no: 1,
        ingredient_id: "i1",
        name: "TEST – Ingredient 1",
        quantity: "100.000",
        unit: "g",
        source_line: null,
        original_text: null,
      },
    ],
    signoffs: [],
    missing_signoffs: ["CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER", "PRODUCT_OWNER"],
    review_items: [],
    ...overrides,
  };
}

const SOP = version({
  id: "bbbbbbbb-0000-0000-0000-000000000002",
  name: "Mini Batata Wada",
  source_menu_id: "MENU008",
  status: "QUARANTINED_DUPLICATE_CANDIDATE",
  is_test_fixture: false,
  open_review_items: 2,
});

describe("recipes list", () => {
  it("lists recipes with status, TEST labels and filters by search and status", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      "GET /api/v1/recipes/versions": () => json([version(), SOP]),
    });
    renderAt("/kitchen/recipes");
    expect(await screen.findByRole("link", { name: "TEST – Synthetic Dish D" })).toBeInTheDocument();
    expect(screen.getAllByTestId("test-badge")).toHaveLength(1);
    expect(within(screen.getByRole("table")).getByText("Quarantined duplicate")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search by name or card ID"), "menu008");
    expect(screen.queryByRole("link", { name: "TEST – Synthetic Dish D" })).not.toBeInTheDocument();
    expect(screen.getByText("1 of 2 recipes")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Search by name or card ID"));
    await userEvent.selectOptions(screen.getByLabelText("Status"), "DRAFT");
    expect(screen.getByRole("link", { name: "TEST – Synthetic Dish D" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Mini Batata Wada" })).not.toBeInTheDocument();
  });

  it("denies accounts without kitchen.recipes.view", async () => {
    mockApi({ "GET /api/v1/me": () => json({ ...KS, permissions: [] }) });
    renderAt("/kitchen/recipes");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });
});

describe("recipe detail", () => {
  it("lets the Kitchen Manager submit with a required reason", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(KM),
      [`GET /api/v1/recipes/versions/${VID}`]: () => json(detail()),
      [`POST /api/v1/recipes/versions/${VID}/transitions`]: () =>
        json(version({ status: "PENDING_VALIDATION" })),
    });
    renderAt(`/kitchen/recipes/${VID}`);
    await userEvent.click(await screen.findByRole("button", { name: "Submit for validation" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm submit" }));
    expect(screen.getByText("Enter at least 3 characters.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Reason for "Submit for validation"'), "ready for chef check");
    await userEvent.click(screen.getByRole("button", { name: "Confirm submit" }));
    expect(await screen.findByText("Submit for validation: done.")).toBeInTheDocument();
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ action: "submit", reason: "ready for chef check" });
  });

  it("shows the backend's refusal message", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KM),
      [`GET /api/v1/recipes/versions/${VID}`]: () => json(detail({ status: "VALIDATED" })),
      [`POST /api/v1/recipes/versions/${VID}/transitions`]: () =>
        json({ code: "http_409", message: "Missing sign-offs: PRODUCT_OWNER" }, 409),
    });
    renderAt(`/kitchen/recipes/${VID}`);
    await userEvent.click(await screen.findByRole("button", { name: "Activate" }));
    expect(screen.getByText(/Missing sign-offs: Chef/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Reason for "Activate"'), "all checks done");
    await userEvent.click(screen.getByRole("button", { name: "Confirm activate" }));
    expect(await screen.findByText("Missing sign-offs: PRODUCT_OWNER")).toBeInTheDocument();
  });

  it("lets the Kitchen Manager record the four kitchen sign-offs, not the product-owner one", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(KM),
      [`GET /api/v1/recipes/versions/${VID}`]: () => json(detail({ status: "PENDING_VALIDATION" })),
      [`POST /api/v1/recipes/versions/${VID}/signoffs`]: () => new Response(null, { status: 204 }),
    });
    renderAt(`/kitchen/recipes/${VID}`);
    const section = await screen.findByRole("region", { name: "Release sign-offs" });
    expect(within(section).getAllByRole("button", { name: "Record sign-off" })).toHaveLength(4);
    expect(section).toHaveTextContent("recorded by a Central Administrator");
    const [first] = within(section).getAllByRole("button", { name: "Record sign-off" });
    if (!first) throw new Error("no sign-off button");
    await userEvent.click(first);
    await userEvent.type(screen.getByLabelText("Note for the Chef sign-off"), "tasted");
    await userEvent.click(within(section).getByRole("button", { name: "Confirm sign-off" }));
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ signoff_type: "CHEF", note: "tasted" });
  });

  it("keeps the confirmation visible after the last step (activation)", async () => {
    let status: RecipeDetail["status"] = "VALIDATED";
    mockApi({
      "GET /api/v1/me": () => json(KM),
      [`GET /api/v1/recipes/versions/${VID}`]: () => json(detail({ status, missing_signoffs: [] })),
      [`POST /api/v1/recipes/versions/${VID}/transitions`]: () => {
        status = "ACTIVE";
        return json(version({ status: "ACTIVE" }));
      },
    });
    renderAt(`/kitchen/recipes/${VID}`);
    await userEvent.click(await screen.findByRole("button", { name: "Activate" }));
    await userEvent.type(screen.getByLabelText('Reason for "Activate"'), "all five recorded");
    await userEvent.click(screen.getByRole("button", { name: "Confirm activate" }));
    expect(await screen.findByText("Activate: done.")).toBeInTheDocument();
    expect(await screen.findByText("No further workflow step applies in this status.")).toBeInTheDocument();
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });

  it("gives Kitchen Staff a read-only view", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KS),
      [`GET /api/v1/recipes/versions/${VID}`]: () => json(detail({ status: "PENDING_VALIDATION" })),
    });
    renderAt(`/kitchen/recipes/${VID}`);
    expect(await screen.findByRole("heading", { name: "TEST – Synthetic Dish D" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Workflow" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record sign-off" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ingredients per serving" })).toHaveTextContent("100.000 g");
  });

  it("shows SOP lineage and the quarantine reason, with no way to submit", async () => {
    mockApi({
      "GET /api/v1/me": () => json(KM),
      [`GET /api/v1/recipes/versions/${SOP.id}`]: () =>
        json(
          detail({
            ...SOP,
            quarantine_reason: "DUPLICATE_BOM: identical ingredient names, quantities and units to MENU057",
            lineage: {
              source_path: "kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md",
              source_sha256: "a".repeat(64),
              source_card_id: "MENU008",
              source_line_start: 120,
              source_line_end: 131,
              source_page_ref: 3,
            },
          }),
        ),
    });
    renderAt(`/kitchen/recipes/${SOP.id}`);
    expect(await screen.findByText(/DUPLICATE_BOM/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Source lineage" })).toHaveTextContent("120–131 (page 3)");
    expect(screen.queryByRole("region", { name: "Workflow" })).not.toBeInTheDocument();
  });
});

describe("review queue", () => {
  const item: ReviewItem = {
    id: "cccccccc-0000-0000-0000-000000000003",
    recipe_version_id: SOP.id,
    recipe_name: "Mini Batata Wada",
    source_card_id: "MENU008",
    reason_code: "MISSING_BATCH_RECIPE",
    subject: "Green chutney (prepared)",
    detail: "Prepared component without a batch recipe or yield",
    source_ref: "KITCHEN_SOURCE_VALIDATION.md §5.1",
    source_line: 125,
    status: "OPEN",
    acknowledged_by: null,
    acknowledged_at: null,
    note: null,
  };

  it("lets the Kitchen Manager acknowledge an item with a note", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(KM),
      "GET /api/v1/recipes/review-items": () => json([item]),
      [`POST /api/v1/recipes/review-items/${item.id}/acknowledge`]: () =>
        json({ ...item, status: "ACKNOWLEDGED", note: "owner to decide" }),
    });
    renderAt("/kitchen/review-queue");
    expect(await screen.findByText(/Missing batch recipe: Prepared component/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    await userEvent.type(screen.getByLabelText('Note for "Green chutney (prepared)"'), "owner to decide");
    await userEvent.click(screen.getByRole("button", { name: "Confirm acknowledgement" }));
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ note: "owner to decide" });
    const list = api.calls.find((r) => r.url.includes("/review-items?"));
    expect(list && new URL(list.url).searchParams.get("status")).toBe("OPEN");
  });

  it("gives Kitchen Staff the list without the acknowledge control", async () => {
    mockApi({ "GET /api/v1/me": () => json(KS), "GET /api/v1/recipes/review-items": () => json([item]) });
    renderAt("/kitchen/review-queue");
    expect(await screen.findByText("Open")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    mockApi({ "GET /api/v1/me": () => json(KS), "GET /api/v1/recipes/review-items": () => json([]) });
    renderAt("/kitchen/review-queue");
    expect(await screen.findByText("No open review items")).toBeInTheDocument();
  });
});
