import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router";

import {
  change,
  csvHref,
  formatKpi,
  useReport,
  type Dataset,
  type Kpi,
  type Report,
  type ReportQuery,
} from "../api";
import { Sparkline } from "./sparkline";
import { useCan } from "@/shared/auth/require-permission";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { formatDateTime, formatPaise } from "@/shared/utils/format";

const DATASETS: { value: Dataset; label: string }[] = [
  { value: "analytics", label: "Real" },
  { value: "analytics_synthetic", label: "Simulated" },
];
// KPIs with a daily series in the report (DDR-117 (9)).
const SERIES: Partial<Record<string, "orders_placed" | "orders_delivered">> = {
  orders_placed: "orders_placed",
  orders_delivered: "orders_delivered",
};

// #10 §10, MG-07, MG-08; DDR-117: ETL spec §9 KPIs over the DDR-75 marts, each with its definition status.
// Nothing here is business truth (DDR-44, class A). Real and simulated data are never mixed (DDR-74).
export function ReportsPage() {
  const [dataset, setDataset] = useState<Dataset>("analytics");
  const [form, setForm] = useState({ from: "", to: "", kitchen: "" });
  const [applied, setApplied] = useState({ from: "", to: "", kitchen: "" });
  const query: ReportQuery = {
    dataset,
    date_from: applied.from || undefined,
    date_to: applied.to || undefined,
    kitchen_id: applied.kitchen || undefined,
  };
  const report = useReport(query);
  const id = useId();

  function apply(event: FormEvent) {
    event.preventDefault();
    setApplied(form);
  }

  const state = queryState(report, { loading: "Loading report…", notFound: "Kitchen not in your scope" });
  const r = report.data;
  return (
    <section className="mx-auto max-w-6xl space-y-5">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Reports &amp; Analytics</h1>
        <p className="text-sm" data-testid="definition-note">
          Every figure follows a formula from the ETL specification and is{" "}
          <span className="font-medium">pending approval (DDR-44)</span>: it is not business truth yet.
        </p>
        {r ? <Freshness r={r} /> : null}
      </header>

      <div role="group" aria-label="Dataset" className="flex flex-wrap gap-2">
        {DATASETS.map((d) => (
          <Button
            key={d.value}
            variant={dataset === d.value ? "primary" : "secondary"}
            aria-pressed={dataset === d.value}
            onClick={() => setDataset(d.value)}
          >
            {d.label}
          </Button>
        ))}
      </div>

      <form
        onSubmit={apply}
        aria-label="Report filters"
        className="grid gap-3 rounded-panel border border-border bg-surface p-3 sm:grid-cols-4"
      >
        <div>
          <label htmlFor={`${id}-from`} className="block text-sm font-medium">
            From
          </label>
          <input
            id={`${id}-from`}
            type="date"
            value={form.from}
            onChange={(e) => setForm({ ...form, from: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-to`} className="block text-sm font-medium">
            To
          </label>
          <input
            id={`${id}-to`}
            type="date"
            value={form.to}
            onChange={(e) => setForm({ ...form, to: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-kitchen`} className="block text-sm font-medium">
            Kitchen
          </label>
          <select
            id={`${id}-kitchen`}
            value={form.kitchen}
            onChange={(e) => setForm({ ...form, kitchen: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          >
            <option value="">All kitchens in your scope</option>
            {(r?.kitchens ?? []).map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Button type="submit">Apply</Button>
          {r?.available ? (
            <Button asChild variant="secondary">
              <a href={csvHref(query)} download>
                Export CSV
              </a>
            </Button>
          ) : null}
        </div>
        <p className="text-xs text-text-muted sm:col-span-4">
          Dates in India Standard Time. Without dates the last 7 days are shown, compared with the 7 days
          before; a range can be at most 31 days.
        </p>
      </form>

      {state ?? (r ? <Body r={r} /> : null)}
    </section>
  );
}

function Freshness({ r }: { r: Report }) {
  const canOperate = useCan("pipelines.operate");
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm" data-testid="freshness">
      {r.fresh_as_of ? `Data as of ${formatDateTime(r.fresh_as_of)}` : "Never built"}
      {r.fresh_as_of && r.stale ? (
        <StatusBadge
          tone="warning"
          label={`Older than ${r.freshness_warn_hours} h (test default, not a final value)`}
        />
      ) : null}
      {canOperate ? (
        <Link to="/management/data-pipelines/p2_elt" className="underline">
          Run P2
        </Link>
      ) : null}
    </p>
  );
}

function Body({ r }: { r: Report }) {
  if (!r.available) {
    return (
      <section
        aria-labelledby="not-built"
        className="rounded-panel border border-dashed border-border bg-surface p-4"
        data-testid="dataset-not-built"
      >
        <h2 id="not-built" className="text-lg font-semibold">
          {r.dataset_label} data: {r.unavailable_reason}
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Labelled simulated data is generated by the P3 pipeline (Task 14) into its own schema, never mixed
          with real data (DDR-74). Nothing on this tab is live.
        </p>
      </section>
    );
  }
  return (
    <div className="space-y-6">
      {r.dataset === "analytics" ? (
        <p className="rounded-panel border border-dashed border-border p-3 text-sm" data-testid="real-note">
          Real data only. Every order in this POC is a TEST order, which real reports never include, so the
          real figures are empty. Simulated data comes with Task 14.
        </p>
      ) : (
        <p className="text-sm font-medium" data-testid="simulated-note">
          Simulated data: generated for the demo, not real orders.
        </p>
      )}
      <p className="text-sm text-text-muted">
        {r.date_from} to {r.date_to}, compared with {r.previous_from} to {r.previous_to}.
      </p>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Key figures">
        {r.kpis.map((k) => (
          <KpiCard key={k.key} kpi={k} series={seriesFor(r, k.key)} />
        ))}
      </ul>

      <section aria-labelledby="daily" className="space-y-2">
        <h2 id="daily" className="text-lg font-semibold">
          Daily
        </h2>
        <div className="overflow-x-auto rounded-panel border border-border bg-surface">
          <table className="w-full text-left text-sm" aria-label="Daily figures">
            <thead className="bg-muted">
              <tr>
                <th scope="col" className="p-2">
                  Date
                </th>
                <th scope="col" className="p-2">
                  Orders placed
                </th>
                <th scope="col" className="p-2">
                  Orders delivered
                </th>
                <th scope="col" className="p-2">
                  Payable
                </th>
                <th scope="col" className="p-2">
                  Discounts
                </th>
              </tr>
            </thead>
            <tbody>
              {r.daily.map((d) => (
                <tr key={d.day} className="border-t border-border">
                  <td className="p-2">{d.day}</td>
                  <td className="p-2">{d.orders_placed}</td>
                  <td className="p-2">{d.orders_delivered}</td>
                  <td className="p-2">{formatPaise(d.payable_paise)}</td>
                  <td className="p-2">{formatPaise(d.discount_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="consumption" className="space-y-2">
        <h2 id="consumption" className="text-lg font-semibold">
          Ingredient consumption
        </h2>
        {r.ingredients.length === 0 ? (
          <p className="text-sm">No consumption in this period.</p>
        ) : (
          <ul className="space-y-1 text-sm" aria-label="Ingredient consumption">
            {r.ingredients.map((i) => (
              <li key={i.ingredient_id}>
                {i.name}: {Number(Number(i.consumed_quantity).toFixed(3))} {i.unit}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="not-available" className="space-y-2">
        <h2 id="not-available" className="text-lg font-semibold">
          Not available
        </h2>
        <ul className="space-y-1 text-sm" aria-label="Not available">
          {r.not_available.map((n) => (
            <li key={n.area}>
              <span className="font-medium">{n.area}</span>: {n.reason}.
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function seriesFor(r: Report, key: string): number[] | undefined {
  const field = SERIES[key];
  return field ? r.daily.map((d) => d[field]) : undefined;
}

function KpiCard({ kpi, series }: { kpi: Kpi; series: number[] | undefined }) {
  const delta = change(kpi.value, kpi.previous);
  return (
    <li className="rounded-panel border border-border bg-surface p-3" data-testid={`kpi-${kpi.key}`}>
      <p className="text-sm text-text-muted">{kpi.label}</p>
      <p className="text-2xl font-semibold">{formatKpi(kpi.unit, kpi.value)}</p>
      <p className="text-xs text-text-muted">
        Previous period: {formatKpi(kpi.unit, kpi.previous)}
        {delta ? ` (${delta})` : ""}
      </p>
      {series ? <Sparkline values={series} label={kpi.label} /> : null}
      <p className="mt-2 text-xs">
        {kpi.formula} · {kpi.source}
      </p>
      <p className="mt-1">
        <StatusBadge tone="warning" label={kpi.definition_status} />
      </p>
      {kpi.denominator_note ? <p className="mt-1 text-xs text-text-muted">{kpi.denominator_note}</p> : null}
    </li>
  );
}
