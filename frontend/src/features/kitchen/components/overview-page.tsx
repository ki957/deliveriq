import { Link } from "react-router";

import { useKitchenQueue, useLowStock, type KitchenQueue } from "../api";
import { PollNote } from "./order-card";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";

const MODE: Record<string, string> = { NORMAL: "Normal", BUSY: "Busy", PAUSED: "Paused" };

/** Mode and capacity (KI-12, KI-13): accepted orders the kitchen holds against the active capacity. */
export function IntakeSummary({ queue }: { queue: KitchenQueue }) {
  const i = queue.intake;
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm" data-testid="intake">
      <StatusBadge
        tone={i.accepting ? "success" : i.refusal === "kitchen_paused" ? "danger" : "warning"}
        label={`Mode: ${MODE[i.mode] ?? i.mode}`}
      />
      <span>
        {i.capacity === null
          ? `${i.active_orders} in progress · not accepting new orders`
          : `${i.active_orders} / ${i.capacity} orders in progress`}
        {i.refusal === "kitchen_at_capacity" ? " · at capacity" : ""}
      </span>
    </p>
  );
}

// KI-U2 Overview.
export function KitchenOverviewPage() {
  const queue = useKitchenQueue();
  const low = useLowStock();
  const state = queryState(queue, { loading: "Loading the kitchen…" });
  if (state) return state;
  if (!queue.data) return null;
  const q = queue.data;
  const preparing = q.held.filter((o) => o.fulfilment_status === "PREPARING").length;
  const ready = q.held.filter((o) => o.fulfilment_status === "READY_FOR_PICKUP").length;
  const tiles = [
    { label: "Incoming", value: q.incoming.length, to: "/kitchen/live-orders" },
    { label: "Overdue", value: q.incoming.filter((o) => o.overdue).length, to: "/kitchen/exceptions" },
    { label: "Accepted", value: q.held.length - preparing - ready, to: "/kitchen/preparation" },
    { label: "Preparing", value: preparing, to: "/kitchen/preparation" },
    { label: "Ready for Pickup", value: ready, to: "/kitchen/preparation" },
    { label: "Low stock", value: low.data?.length ?? 0, to: "/kitchen/inventory" },
  ];

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Overview · {q.kitchen_name}</h1>
        <PollNote updatedAt={queue.dataUpdatedAt} />
      </header>
      <IntakeSummary queue={q} />
      <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6" aria-label="Kitchen summary">
        {tiles.map((t) => (
          <li key={t.label}>
            <Link
              to={t.to}
              className="flex min-h-24 flex-col justify-center rounded-panel border border-border bg-surface p-4 hover:bg-muted"
            >
              <span className="text-3xl font-semibold">{t.value}</span>
              <span className="text-sm text-text-muted">{t.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
