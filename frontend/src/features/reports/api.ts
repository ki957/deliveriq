import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

export type Report = components["schemas"]["ReportOut"];
export type Kpi = components["schemas"]["KpiOut"];
export type Dataset = Report["dataset"];

export type ReportQuery = {
  dataset: Dataset;
  date_from?: string | undefined;
  date_to?: string | undefined;
  kitchen_id?: string | undefined;
};

function clean(q: ReportQuery): Record<string, string> {
  return Object.fromEntries(Object.entries(q).filter(([, v]) => v !== undefined && v !== "")) as Record<
    string,
    string
  >;
}

/** DDR-117: marts change only when P2 runs, so reports do not poll. */
export function useReport(q: ReportQuery) {
  return useQuery({
    queryKey: ["reports", q],
    queryFn: async () => unwrap(await api.GET("/api/v1/management/reports", { params: { query: clean(q) } })),
    placeholderData: keepPreviousData,
  });
}

/** Same-origin CSV link with the current view (DDR-117 (10)); scope and limits are enforced by the server. */
export function csvHref(q: ReportQuery): string {
  return `/api/v1/management/reports.csv?${new URLSearchParams(clean(q)).toString()}`;
}

/** Display a KPI value in its unit; null means no qualifying records (never an invented value, MG-08). */
export function formatKpi(unit: Kpi["unit"], value: number | null | undefined): string {
  if (value === null || value === undefined) return "No value";
  switch (unit) {
    case "paise":
      return `₹${(value / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
    case "seconds": {
      const s = Math.round(value);
      return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
    }
    case "ratio":
      return `${(value * 100).toLocaleString("en-IN", { maximumFractionDigits: 1 })}%`;
    default:
      return value.toLocaleString("en-IN");
  }
}

/** "+12%" against the previous period; nothing when either side has no value or the previous is 0. */
export function change(value: number | null | undefined, previous: number | null | undefined): string | null {
  if (
    value === null ||
    value === undefined ||
    previous === null ||
    previous === undefined ||
    previous === 0
  ) {
    return null;
  }
  const pct = ((value - previous) / Math.abs(previous)) * 100;
  return `${pct > 0 ? "+" : ""}${pct.toLocaleString("en-IN", { maximumFractionDigits: 1 })}%`;
}
