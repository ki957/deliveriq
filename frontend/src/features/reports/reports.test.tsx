import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { change, formatKpi, type Kpi, type Report } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

const KITCHEN = "k0k0k0k0-0000-0000-0000-000000000001";
const RM = me({
  display_name: "Demo Regional Manager",
  roles: [{ role: "REGIONAL_MANAGER", region_id: "r1", kitchen_id: null }],
  permissions: ["management.reports.view", "management.operations.view"],
  portals: ["management"],
});

function kpi(overrides: Partial<Kpi>): Kpi {
  return {
    key: "orders_placed",
    label: "Orders placed",
    unit: "count",
    value: 12,
    previous: 10,
    formula: "Distinct eligible order IDs",
    source: "ETL spec §9.6 order count",
    definition_status: "Definition pending approval (DDR-44)",
    denominator_note: null,
    ...overrides,
  };
}

function report(overrides: Partial<Report> = {}): Report {
  return {
    dataset: "analytics",
    dataset_label: "Real",
    available: true,
    unavailable_reason: null,
    fresh_as_of: "2026-11-10T10:00:00Z",
    generated_from: null,
    generated_to: null,
    freshness_warn_hours: 24,
    stale: true,
    date_from: "2026-11-06",
    date_to: "2026-11-12",
    previous_from: "2026-10-30",
    previous_to: "2026-11-05",
    kitchens: [{ id: KITCHEN, name: "Chennai Kitchen" }],
    kitchen_id: null,
    kpis: [
      kpi({}),
      kpi({
        key: "rejection_rate",
        label: "Rejection rate",
        unit: "ratio",
        value: null,
        previous: null,
        formula: "Rejected orders ÷ orders the kitchen accepted or rejected",
        source: "ETL spec §9.4",
        denominator_note: "Denominator chosen for the POC, pending approval (DDR-117 (2))",
      }),
    ],
    daily: [
      { day: "2026-11-11", orders_placed: 5, orders_delivered: 4, payable_paise: 50000, discount_paise: 0 },
      { day: "2026-11-12", orders_placed: 7, orders_delivered: 6, payable_paise: 70000, discount_paise: 500 },
    ],
    ingredients: [{ ingredient_id: "i1", name: "Rice", unit: "g", consumed_quantity: "1500.000" }],
    not_available: [
      { area: "Promotions (usage, discount, resulting orders)", reason: "No promotion model (DDR-114 (2))" },
    ],
    kpis_are_business_truth: false,
    ...overrides,
  };
}

describe("reports (DDR-117)", () => {
  it("offers the generated simulated dates without silently changing filters", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/management/reports/forecast": () =>
        json({
          available: false,
          unavailable_reason: "The P3 ML profile is not ready",
          trained_on: "simulated data",
          advisory_only: true,
          profile_from: null,
          profile_to: null,
          backtest_model_mae: null,
          backtest_baseline_mae: null,
          backtest_passed: false,
          forecasts: [],
        }),
      "GET /api/v1/management/reports": (request) =>
        json(
          new URL(request.url).searchParams.get("dataset") === "analytics_synthetic"
            ? report({
                dataset: "analytics_synthetic",
                dataset_label: "Simulated",
                generated_from: "2026-11-07",
                generated_to: "2026-11-13",
              })
            : report(),
        ),
    });
    renderAt("/management/reports");
    await userEvent.click(await screen.findByRole("button", { name: "Simulated" }));
    expect(await screen.findByTestId("demo-dates")).toHaveTextContent("2026-11-07 to 2026-11-13");
    expect(screen.getByLabelText("From")).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Use demo dates" }));
    expect(screen.getByLabelText("From")).toHaveValue("2026-11-07");
    expect(screen.getByLabelText("To")).toHaveValue("2026-11-13");
  });

  it("shows the forecast only on simulated reports and states its limits", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/management/reports": (request) =>
        json(
          new URL(request.url).searchParams.get("dataset") === "analytics_synthetic"
            ? report({ dataset: "analytics_synthetic", dataset_label: "Simulated" })
            : report(),
        ),
      "GET /api/v1/management/reports/forecast": () =>
        json({
          available: true,
          unavailable_reason: null,
          trained_on: "simulated data",
          advisory_only: true,
          profile_from: "2026-08-15",
          profile_to: "2026-11-12",
          backtest_model_mae: 2.1,
          backtest_baseline_mae: 2.4,
          backtest_passed: true,
          forecasts: [
            {
              ingredient_id: "i1",
              name: "Rice",
              unit: "g",
              daily: [
                { day: "2026-11-13", quantity: 12 },
                { day: "2026-11-14", quantity: 13 },
                { day: "2026-11-15", quantity: 14 },
                { day: "2026-11-16", quantity: 15 },
                { day: "2026-11-17", quantity: 16 },
                { day: "2026-11-18", quantity: 17 },
                { day: "2026-11-19", quantity: 18 },
              ],
            },
          ],
        }),
    });
    renderAt("/management/reports");
    await userEvent.click(await screen.findByRole("button", { name: "Simulated" }));
    expect(
      await screen.findByRole("table", { name: "Seven-day ingredient demand forecast" }),
    ).toHaveTextContent("Rice (g)");
    expect(screen.getByTestId("forecast-backtest")).toHaveTextContent("model MAE 2.100 < baseline MAE 2.400");
    expect(screen.getByText(/Trained on simulated data · Advisory only/)).toBeInTheDocument();
  });
  it("shows each KPI with its formula, source and pending-approval status, and labels real data", async () => {
    mockApi({ "GET /api/v1/me": () => json(RM), "GET /api/v1/management/reports": () => json(report()) });
    renderAt("/management/reports");
    const cards = await screen.findByRole("list", { name: "Key figures" });
    const orders = within(cards).getByTestId("kpi-orders_placed");
    expect(orders).toHaveTextContent("12");
    expect(orders).toHaveTextContent("Previous period: 10 (+20%)");
    expect(orders).toHaveTextContent("Distinct eligible order IDs · ETL spec §9.6 order count");
    expect(orders).toHaveTextContent("Definition pending approval (DDR-44)");
    expect(within(orders).getByRole("figure")).toHaveAccessibleName(
      "Orders placed: daily values 5, 7 (total 12)",
    );
    const rate = within(cards).getByTestId("kpi-rejection_rate");
    expect(rate).toHaveTextContent("No value");
    expect(rate).toHaveTextContent("Denominator chosen for the POC, pending approval");
    expect(screen.getByTestId("real-note")).toHaveTextContent("Every order in this POC is a TEST order");
    expect(screen.getByTestId("freshness")).toHaveTextContent(
      "Older than 24 h (test default, not a final value)",
    );
    expect(screen.queryByRole("link", { name: "Run P2" })).not.toBeInTheDocument(); // RM: no pipeline control
    expect(screen.getByRole("table", { name: "Daily figures" })).toHaveTextContent("₹700");
    expect(screen.getByRole("list", { name: "Ingredient consumption" })).toHaveTextContent("Rice: 1500 g");
    expect(screen.getByRole("list", { name: "Not available" })).toHaveTextContent("Promotions");
  });

  it("sends the filters, exports the same view and keeps the simulated tab separate", async () => {
    const { calls } = mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/management/reports": (r) =>
        json(
          new URL(r.url).searchParams.get("dataset") === "analytics_synthetic"
            ? report({ dataset: "analytics_synthetic", dataset_label: "Simulated", available: false,
                       unavailable_reason: "Not built yet (Task 14)", kpis: [], daily: [], ingredients: [] }) // prettier-ignore
            : report(),
        ),
    });
    renderAt("/management/reports");
    await screen.findByRole("list", { name: "Key figures" });
    await userEvent.type(screen.getByLabelText("From"), "2026-11-01");
    await userEvent.type(screen.getByLabelText("To"), "2026-11-03");
    await userEvent.selectOptions(screen.getByLabelText("Kitchen"), KITCHEN);
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => {
      const last = calls.filter((c) => c.url.includes("/management/reports")).at(-1);
      expect(last?.url).toContain(`date_from=2026-11-01&date_to=2026-11-03&kitchen_id=${KITCHEN}`);
    });
    expect(screen.getByRole("link", { name: "Export CSV" }).getAttribute("href")).toBe(
      `/api/v1/management/reports.csv?dataset=analytics&date_from=2026-11-01&date_to=2026-11-03&kitchen_id=${KITCHEN}`,
    );
    await userEvent.click(screen.getByRole("button", { name: "Simulated" }));
    expect(await screen.findByTestId("dataset-not-built")).toHaveTextContent(
      "Simulated data: Not built yet (Task 14)",
    );
    expect(screen.getByRole("button", { name: "Simulated" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("link", { name: "Export CSV" })).not.toBeInTheDocument();
  });

  it("is not in the navigation without management.reports.view", async () => {
    mockApi({
      "GET /api/v1/me": () => json({ ...RM, permissions: ["management.operations.view"] }),
      "GET /api/v1/management/overview": () => json({}, 500),
    });
    renderAt("/management/reports");
    expect(await screen.findByText("You don't have access to this area")).toBeInTheDocument();
    const [nav] = screen.getAllByRole("navigation", { name: "Management navigation" });
    expect(
      within(nav as HTMLElement).queryByRole("link", { name: "Reports & Analytics" }),
    ).not.toBeInTheDocument();
  });

  it("formats values in their unit and never invents a change", () => {
    expect(formatKpi("paise", 123450)).toBe("₹1,234.5");
    expect(formatKpi("seconds", 75)).toBe("1 min 15 s");
    expect(formatKpi("ratio", 0.2222)).toBe("22.2%");
    expect(formatKpi("count", null)).toBe("No value");
    expect(change(12, 10)).toBe("+20%");
    expect(change(5, 0)).toBeNull();
    expect(change(null, 3)).toBeNull();
  });
});
