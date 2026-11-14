import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { isActive, pollInterval, POLL_MS, type Pipeline, type Run, type RunDetail } from "./api";
import { json, me, mockApi, renderAt } from "@/test/render";

const RUN_ID = "11111111-2222-3333-4444-555555555555";
const CA = me({
  roles: [{ role: "CENTRAL_ADMIN", region_id: null, kitchen_id: null }],
  permissions: ["pipelines.view", "pipelines.operate"],
  portals: ["management"],
});
const RM = me({
  roles: [{ role: "REGIONAL_MANAGER", region_id: "r1", kitchen_id: null }],
  permissions: ["pipelines.view"],
  portals: ["management"],
});

function run(overrides: Partial<Run> = {}): Run {
  return {
    id: RUN_ID,
    pipeline: "p1_sop",
    status: "completed_with_quarantine",
    trigger: "ui",
    is_test: true,
    input_ref: "fault:records",
    region_id: "r1",
    retry_of: null,
    failure_class: null,
    error_summary: null,
    cancel_requested: false,
    counts: { cards: 7, quarantined_records: 5 },
    queued_at: "2026-11-12T10:00:00Z",
    started_at: "2026-11-12T10:00:01Z",
    finished_at: "2026-11-12T10:00:02Z",
    has_report: true,
    ...overrides,
  };
}

const PIPELINES: Pipeline[] = [
  {
    name: "p1_sop",
    display_name: "P1 SOP master-data ETL",
    pipeline_group: "DATA",
    is_heavy: false,
    implemented: true,
    inputs: ["sop", "fault:records", "fault:structural"],
    last_run: run(),
  },
  {
    name: "p2_elt",
    display_name: "P2 operational ELT",
    pipeline_group: "DATA",
    is_heavy: true,
    implemented: true,
    inputs: ["run", "fault:reconciliation"],
    last_run: null,
  },
  {
    name: "k2_kitchen",
    display_name: "K2 Kitchen knowledge",
    pipeline_group: "KNOWLEDGE",
    is_heavy: true,
    implemented: false,
    inputs: [],
    last_run: null,
  },
];

function detail(overrides: Partial<Run> = {}): RunDetail {
  return {
    run: run(overrides),
    stages: [
      {
        seq: 1,
        stage: "register",
        status: "succeeded",
        rows_in: null,
        rows_out: null,
        rows_rejected: null,
        detail: {},
        started_at: "2026-11-12T10:00:01Z",
        finished_at: "2026-11-12T10:00:01.200Z",
      },
      {
        seq: 2,
        stage: "quality checks",
        status: "succeeded",
        rows_in: 7,
        rows_out: null,
        rows_rejected: 6,
        detail: {},
        started_at: "2026-11-12T10:00:01.200Z",
        finished_at: "2026-11-12T10:00:01.500Z",
      },
    ],
    errors: [
      {
        stage: "quality checks",
        record_ref: "TEST – Fault Card 01@12",
        reason_code: "MISSING_UNIT",
        message: "- TEST – Fault ingredient A: 50",
      },
    ],
    errors_total: 1,
    dq_results: [
      { check_name: "unique_card_ids", severity: "critical", status: "fail", failures: 1, detail: {} },
    ],
  };
}

describe("polling", () => {
  it("polls every 2 s only while a run is queued or running", () => {
    expect(isActive(run({ status: "running" }))).toBe(true);
    expect(isActive(run({ status: "queued" }))).toBe(true);
    expect(isActive(run({ status: "failed" }))).toBe(false);
    expect(isActive(null)).toBe(false);
    expect(pollInterval(true)).toBe(POLL_MS);
    expect(POLL_MS).toBe(2000);
    expect(pollInterval(false)).toBe(false);
  });
});

describe("P2 page (DDR-116 (7)–(10))", () => {
  const status = {
    freshness: { dataset: "analytics", fresh_as_of: "2026-11-12T10:00:00Z", run_id: RUN_ID },
    schedule: {
      enabled: false,
      interval_minutes: 60,
      interval_is_test_default: true,
      updated_at: "2026-11-12T09:00:00Z",
    },
    intervals: [15, 30, 60, 240],
  };

  it("lets a Central Administrator turn the timer on with a reason", async () => {
    const { calls } = mockApi({
      "GET /api/v1/me": () => json(CA),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/runs": () => json([]),
      "GET /api/v1/pipelines/p2/status": () => json(status),
      "PUT /api/v1/pipelines/p2/schedule": () =>
        json({ ...status, schedule: { ...status.schedule, enabled: true } }),
    });
    renderAt("/management/data-pipelines/p2_elt");
    expect(await screen.findByTestId("freshness")).toHaveTextContent("Real marts fresh as of:");
    expect(screen.getByTestId("real-marts-note")).toHaveTextContent(
      "Every order in this POC is a TEST order",
    );
    expect(screen.getByTestId("schedule")).toHaveTextContent(
      "off, every 60 min (test default, not a final value)",
    );
    expect(screen.getByLabelText("Input")).toHaveDisplayValue("Build analytics from landed events");
    await userEvent.click(screen.getByLabelText("Run P2 on a timer"));
    await userEvent.selectOptions(screen.getByLabelText("Every"), "30");
    await userEvent.click(screen.getByRole("button", { name: "Review and save" }));
    await userEvent.type(
      screen.getByLabelText("Why are you changing the P2 schedule?"),
      "Nightly demo refresh",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save schedule" }));
    expect(await screen.findByText("Schedule saved.")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    expect(await put?.json()).toEqual({
      enabled: true,
      interval_minutes: 30,
      reason: "Nightly demo refresh",
    });
  });

  it("shows a Regional Manager freshness only: no run controls, schedule form or runs", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/runs": () => json([]),
      "GET /api/v1/pipelines/p2/status": () => json(status),
    });
    renderAt("/management/data-pipelines/p2_elt");
    expect(await screen.findByTestId("freshness")).toBeInTheDocument();
    expect(screen.queryByLabelText("Run P2 on a timer")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run pipeline" })).not.toBeInTheDocument();
    expect(
      await screen.findByText("P2 runs cover every region: only a Central Administrator sees them"),
    ).toBeInTheDocument();
  });
});

describe("P2 outbox backlog (DDR-116 (10), (12))", () => {
  const backlog = {
    waiting: 3,
    oldest_waiting_at: "2026-11-12T10:00:00Z",
    oldest_age_seconds: 420,
    landed: 3472,
    rejected: 1,
    warn_after_seconds: 300,
    warn_is_test_default: true,
  };

  it("shows a Central Administrator the backlog, its age and a labelled warning", async () => {
    mockApi({
      "GET /api/v1/me": () => json(CA),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/p2/backlog": () => json(backlog),
    });
    renderAt("/management/data-pipelines");
    const figures = await screen.findByTestId("backlog");
    expect(figures).toHaveTextContent("Waiting3");
    expect(figures).toHaveTextContent("Oldest waiting7 min");
    expect(figures).toHaveTextContent("Landed3472");
    expect(figures).toHaveTextContent("Rejected (kept)1");
    expect(screen.getByText("Backlog older than 5 min")).toBeInTheDocument();
    expect(screen.getByText(/Warning after 5 min \(test default, not a final value\)/)).toBeInTheDocument();
  });

  it("shows a Regional Manager no backlog and never asks for it", async () => {
    const { calls } = mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/pipelines": () => json(PIPELINES),
    });
    renderAt("/management/data-pipelines");
    expect(await screen.findByRole("region", { name: "Data" })).toBeInTheDocument();
    expect(screen.queryByTestId("backlog")).not.toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("backlog"))).toBe(false);
  });
});

describe("Data & Pipelines overview", () => {
  it("groups pipelines, shows the last persisted status and labels unbuilt pipelines with their task", async () => {
    mockApi({ "GET /api/v1/me": () => json(RM), "GET /api/v1/pipelines": () => json(PIPELINES) });
    renderAt("/management/data-pipelines");
    expect(await screen.findByRole("heading", { name: "Data & Pipelines", level: 1 })).toBeInTheDocument();
    const data = screen.getByRole("region", { name: "Data" });
    expect(within(data).getByRole("link", { name: "P1 SOP master-data ETL" })).toBeInTheDocument();
    expect(within(data).getByText("Completed with quarantine")).toBeInTheDocument();
    expect(within(data).getByText("Test run")).toBeInTheDocument();
    expect(within(data).getByRole("link", { name: "P2 operational ELT" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Knowledge" })).toHaveTextContent("Not built yet (Task 16)");
  });

  it("shows the denied state without pipelines.view and when the backend refuses", async () => {
    mockApi({ "GET /api/v1/me": () => json({ ...RM, permissions: [] }) });
    renderAt("/management/data-pipelines");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });

  it("maps a backend 403 to the denied state and other failures to the error state", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/pipelines": () => json({ code: "http_403", message: "Forbidden" }, 403),
    });
    renderAt("/management/data-pipelines");
    expect(await screen.findByRole("alert")).toHaveTextContent("You don't have access to this area");
  });

  it("shows an error state when the list cannot load", async () => {
    mockApi({ "GET /api/v1/me": () => json(RM), "GET /api/v1/pipelines": () => json({}, 500) });
    renderAt("/management/data-pipelines");
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});

describe("pipeline page", () => {
  it("lets a Central Administrator run P1 with a labelled TEST fault input", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(CA),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/runs": () => json([run()]),
      "POST /api/v1/pipelines/runs": () => json(run({ status: "queued" }), 202),
      [`GET /api/v1/pipelines/runs/${RUN_ID}`]: () => json(detail({ status: "queued" })),
    });
    const router = renderAt("/management/data-pipelines/p1_sop");
    const select = await screen.findByLabelText("Input");
    expect(
      within(select)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual([
      "Kitchen SOP (committed copy)",
      "TEST – fault file: record faults",
      "TEST – fault file: broken structure",
    ]);
    await userEvent.selectOptions(select, "fault:records");
    expect(screen.getByText(/TEST fault files are written from scratch/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run pipeline" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/management/data-pipelines/runs/${RUN_ID}`),
    );
    const post = api.calls.find((r) => r.method === "POST");
    expect(await post?.json()).toEqual({ pipeline: "p1_sop", input_ref: "fault:records" });
    expect(post?.headers.get("X-DeliverIQ-CSRF")).toBe("1");
  });

  it("gives a Regional Manager run history without any action control", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/runs": () => json([run()]),
    });
    renderAt("/management/data-pipelines/p1_sop");
    expect(await screen.findByRole("link", { name: "View run" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run pipeline" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Input")).not.toBeInTheDocument();
  });

  it("shows an empty history", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/runs": () => json([]),
    });
    renderAt("/management/data-pipelines/p1_sop");
    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
  });

  it("filters the run history by status and test/real (DDR-114 (13))", async () => {
    const real = run({ id: "22222222-2222-3333-4444-555555555555", status: "failed", is_test: false });
    mockApi({
      "GET /api/v1/me": () => json(RM),
      "GET /api/v1/pipelines": () => json(PIPELINES),
      "GET /api/v1/pipelines/runs": () => json([run(), real]),
    });
    renderAt("/management/data-pipelines/p1_sop");
    expect(await screen.findAllByRole("link", { name: "View run" })).toHaveLength(2);
    await userEvent.selectOptions(screen.getByLabelText("Runs"), "real");
    expect(screen.getAllByRole("link", { name: "View run" })).toHaveLength(1);
    expect(screen.getByTestId("run-filters")).toHaveTextContent("Filters the latest 2 runs · showing 1");
    await userEvent.selectOptions(screen.getByLabelText("Status"), "completed_with_quarantine");
    expect(await screen.findByText("No runs match these filters")).toBeInTheDocument();
  });
});

describe("run detail", () => {
  it("shows stages, quarantined records with reasons, quality results and the report link", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      [`GET /api/v1/pipelines/runs/${RUN_ID}`]: () => json(detail()),
    });
    renderAt(`/management/data-pipelines/runs/${RUN_ID}`);
    expect(await screen.findByText("Completed with quarantine")).toBeInTheDocument();
    expect(screen.getByText("Test run")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Stages" })).toHaveTextContent("2. quality checks");
    const errors = screen.getByRole("region", { name: "Quarantined records and errors" });
    expect(errors).toHaveTextContent("TEST – Fault Card 01@12");
    expect(errors).toHaveTextContent("MISSING_UNIT");
    expect(screen.getByRole("region", { name: "Quality checks" })).toHaveTextContent("Unique card ids");
    expect(screen.getByTestId("count-cards")).toHaveTextContent("7");
    expect(screen.getByRole("link", { name: "Download report" })).toHaveAttribute(
      "href",
      `/api/v1/pipelines/runs/${RUN_ID}/report`,
    );
    // Regional Manager: view only.
    expect(screen.queryByRole("button", { name: /Retry|Cancel/ })).not.toBeInTheDocument();
  });

  it("lets a Central Administrator cancel an active run and retry a failed one", async () => {
    const api = mockApi({
      "GET /api/v1/me": () => json(CA),
      [`GET /api/v1/pipelines/runs/${RUN_ID}`]: () => json(detail({ status: "queued", has_report: false })),
      [`POST /api/v1/pipelines/runs/${RUN_ID}/cancel`]: () => json({ outcome: "cancelled" }),
    });
    renderAt(`/management/data-pipelines/runs/${RUN_ID}`);
    expect(await screen.findByText(/Refreshing every 2 seconds/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry run" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel run" }));
    expect(await screen.findByText("Run cancelled.")).toBeInTheDocument();
    expect(api.calls.some((r) => r.method === "POST" && r.url.endsWith("/cancel"))).toBe(true);
  });

  it("offers retry on a failed run and opens the new run", async () => {
    const newId = "99999999-2222-3333-4444-555555555555";
    mockApi({
      "GET /api/v1/me": () => json(CA),
      [`GET /api/v1/pipelines/runs/${RUN_ID}`]: () =>
        json(detail({ status: "failed", failure_class: "structural", error_summary: "Structure invalid" })),
      [`POST /api/v1/pipelines/runs/${RUN_ID}/retry`]: () => json(run({ id: newId, status: "queued" }), 202),
      [`GET /api/v1/pipelines/runs/${newId}`]: () => json(detail({ id: newId, status: "queued" })),
    });
    const router = renderAt(`/management/data-pipelines/runs/${RUN_ID}`);
    expect(await screen.findByText("Structure invalid")).toBeInTheDocument();
    expect(screen.getByText("Structural")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry run" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/management/data-pipelines/runs/${newId}`),
    );
  });

  it("shows not found for an unknown or out-of-scope run", async () => {
    mockApi({
      "GET /api/v1/me": () => json(RM),
      [`GET /api/v1/pipelines/runs/${RUN_ID}`]: () => json({ code: "not_found", message: "Not found" }, 404),
    });
    renderAt(`/management/data-pipelines/runs/${RUN_ID}`);
    expect(await screen.findByText("Run not found")).toBeInTheDocument();
  });
});
