import { Link } from "react-router";

import { ORDER_STATUSES, useOverview, type KitchenStatus } from "../api";
import { PageHeader, TableBox, Td, Th } from "./common";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { humanize } from "@/shared/utils/format";

// Non-terminal statuses (Matrix §7.3); delivered, cancelled, rejected and failed are not "active".
const ACTIVE = [
  "PLACED",
  "PENDING_KITCHEN",
  "ACCEPTED",
  "PREPARING",
  "READY_FOR_PICKUP",
  "PICKED_UP",
  "OUT_FOR_DELIVERY",
];

// #10 §13, DDR-114 (10): counts from persisted data only; revenue and KPIs are Task 13 (DDR-44).
export function ManagementOverviewPage() {
  const overview = useOverview();
  const state = queryState(overview, { loading: "Loading overview…" });
  if (state) return state;
  const o = overview.data;
  if (!o) return null;
  const counts = ORDER_STATUSES.filter((s) => ACTIVE.includes(s.value));
  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Overview" updatedAt={overview.dataUpdatedAt}>
        <p className="text-sm text-text-muted">
          Your scope only. Counts come from stored orders and requests.
        </p>
      </PageHeader>

      <section aria-labelledby="active-orders">
        <h2 id="active-orders" className="text-lg font-semibold">
          Active orders by status
        </h2>
        <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {counts.map((s) => (
            <li key={s.value} className="rounded-panel border border-border bg-surface p-3">
              <p className="text-sm text-text-muted">{s.label}</p>
              <p className="text-2xl font-semibold" data-testid={`count-${s.value}`}>
                {o.orders_by_status[s.value] ?? 0}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="attention">
        <h2 id="attention" className="text-lg font-semibold">
          Needs attention
        </h2>
        <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <Attention
            label="Overdue incoming orders"
            value={o.overdue_incoming}
            to="/management/orders?status=PENDING_KITCHEN"
          />
          <Attention
            label="Delivery exceptions open"
            value={o.delivery_exceptions}
            to="/management/orders?exception=true"
          />
          <Attention
            label="Failure requests to decide"
            value={o.failure_requests}
            to="/management/delivery"
          />
          <Attention
            label="Dish availability requests"
            value={o.availability_requests}
            to="/management/dish-availability"
          />
          <Attention label="Agents online" value={o.online_agents} to="/management/delivery" />
          <Attention label="Active deliveries" value={o.active_deliveries} to="/management/delivery" />
        </ul>
      </section>

      <section aria-labelledby="kitchens">
        <h2 id="kitchens" className="text-lg font-semibold">
          Kitchens
        </h2>
        <div className="mt-2">
          <KitchenTable kitchens={o.kitchens} />
        </div>
      </section>

      <p className="rounded-panel border border-dashed border-border p-3 text-sm" data-testid="kpi-note">
        Revenue, trends and KPIs are not shown: their formulas are not defined yet (DDR-44). They come with
        Reports &amp; Analytics in Task 13.
      </p>
    </section>
  );
}

function Attention({ label, value, to }: { label: string; value: number; to: string }) {
  return (
    <li className="rounded-panel border border-border bg-surface p-3">
      <Link to={to} className="flex items-center justify-between gap-2 underline-offset-2 hover:underline">
        <span>{label}</span>
        <span className="text-xl font-semibold">{value}</span>
      </Link>
    </li>
  );
}

export function KitchenTable({ kitchens }: { kitchens: KitchenStatus[] }) {
  if (kitchens.length === 0) return <p className="text-sm">No kitchens in your scope.</p>;
  return (
    <TableBox label="Kitchens">
      <thead className="bg-muted">
        <tr>
          <Th>Kitchen</Th>
          <Th>Region</Th>
          <Th>Mode</Th>
          <Th>Intake</Th>
        </tr>
      </thead>
      <tbody>
        {kitchens.map((k) => (
          <tr key={k.id} className="border-t border-border">
            <Td>
              {k.name}
              <span className="block text-xs text-text-muted">{k.code}</span>
            </Td>
            <Td>{k.region_name}</Td>
            <Td>
              <StatusBadge
                tone={k.mode === "PAUSED" ? "danger" : k.mode === "BUSY" ? "warning" : "neutral"}
                label={humanize(k.mode)}
              />
            </Td>
            <Td>
              {k.intake ? (
                <>
                  {k.intake.active_orders} of {k.intake.capacity ?? "—"} active ·{" "}
                  {k.intake.accepting ? "accepting" : `not accepting (${humanize(k.intake.refusal ?? "")})`}
                </>
              ) : (
                "Capacity not configured"
              )}
            </Td>
          </tr>
        ))}
      </tbody>
    </TableBox>
  );
}
