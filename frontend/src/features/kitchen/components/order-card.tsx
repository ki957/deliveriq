import type { ReactNode } from "react";

import type { KitchenOrder } from "../api";
import { minutesSince, shortId, statusTone } from "../format";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime } from "@/shared/utils/format";

const PAYMENT: Record<string, string> = {
  COD: "Cash on Delivery",
  SIM_UPI: "UPI (Simulation)",
  SIM_CARD: "Card (Simulation)",
};

// DDR-112 (3): who will carry the order. Offers come from kitchen acceptance (DDR-51).
export function AgentLine({ order }: { order: KitchenOrder }) {
  if (order.fulfilment_status === "PENDING_KITCHEN") return null;
  const a = order.assignment;
  const text = !a
    ? "Awaiting agent"
    : a.status === "ACCEPTED"
      ? `Agent assigned: ${a.agent_name}`
      : `Offered to ${a.agent_name}`;
  return <p className="text-sm text-text-muted">{text}</p>;
}

/** KI-07 card: order, times, items with pinned recipe version, instructions, status, warnings. */
export function OrderCard({
  order,
  now,
  children,
}: {
  order: KitchenOrder;
  now: number;
  children?: ReactNode;
}) {
  const waiting = minutesSince(order.queued_at ?? order.placed_at, now);
  return (
    <article
      aria-labelledby={`order-${order.id}`}
      className="rounded-panel border border-border bg-surface p-4"
      data-testid="kitchen-order"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`order-${order.id}`} className="text-lg font-semibold">
          Order {shortId(order.id)}
        </h3>
        <span className="flex flex-wrap items-center gap-2">
          {order.is_test_fixture ? <TestBadge label="Test order" /> : null}
          {order.overdue ? (
            <StatusBadge tone="danger" label={`Overdue · waiting ${waiting ?? 0} min`} />
          ) : null}
          <StatusBadge tone={statusTone(order.fulfilment_status)} label={order.status_label} />
        </span>
      </header>
      <p className="mt-1 text-sm text-text-muted">
        {order.accepted_at
          ? `Accepted ${formatDateTime(order.accepted_at)}`
          : `In queue since ${formatDateTime(order.queued_at)}`}
        {order.payment_method ? ` · ${PAYMENT[order.payment_method] ?? order.payment_method}` : ""}
      </p>
      <ul className="mt-2 space-y-1 text-sm" aria-label={`Items in order ${shortId(order.id)}`}>
        {order.items.map((i) => (
          <li key={i.id}>
            <span className="font-medium">
              {i.quantity} × {i.item_name}
            </span>
            {i.recipe_version ? <span className="text-text-muted"> · recipe v{i.recipe_version}</span> : null}
          </li>
        ))}
      </ul>
      {order.special_instructions ? (
        <p className="mt-2 rounded-control bg-muted p-2 text-sm">
          Instructions: {order.special_instructions}
        </p>
      ) : null}
      <div className="mt-2">
        <AgentLine order={order} />
      </div>
      {children}
    </article>
  );
}

/** DDR-111 (6), DDR-112 (3): one note per page while agents are simulated. */
export function AgentNote() {
  return (
    <p className="text-xs text-text-muted">
      Agent availability is simulated until Task 9: every active agent counts as available.
    </p>
  );
}
