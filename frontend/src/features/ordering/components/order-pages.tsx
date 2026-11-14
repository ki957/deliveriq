import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  Refusal,
  useCancelOrder,
  useOrder,
  useOrders,
  useSimulatePayment,
  type Order,
  type SimOutcome,
} from "../api";
import { useRealtimeStatus } from "@/shared/realtime/use-live";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge, type StatusTone } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, formatPaise, humanize } from "@/shared/utils/format";

// Customer labels come from the backend's canonical display mapping (Matrix §7.3); only the tone is local.
function tone(status: Order["fulfilment_status"]): StatusTone {
  if (status === "DELIVERED") return "success";
  if (status === "CANCELLED" || status === "REJECTED" || status === "DELIVERY_FAILED") return "danger";
  if (status === "PLACED") return "neutral";
  return "info";
}

const PAYMENT_LABELS: Record<string, string> = {
  SIM_UPI: "UPI (Simulation)",
  SIM_CARD: "Card (Simulation)",
  COD: "Cash on Delivery",
};

export function OrdersPage() {
  const orders = useOrders();
  const state = queryState(orders, { loading: "Loading your orders…" });
  if (state) return state;
  const list = orders.data ?? [];
  return (
    <section className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">My Orders</h1>
      {list.length === 0 ? (
        <EmptyState title="No orders yet">
          <Link to="/customer/menu" className="underline">
            Browse the menu
          </Link>
        </EmptyState>
      ) : (
        <ul className="mt-4 divide-y divide-border rounded-panel border border-border bg-surface">
          {list.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
              <div>
                <Link to={`/customer/orders/${o.id}`} className="font-medium underline">
                  Order {o.id.slice(0, 8)}
                </Link>
                <p className="text-text-muted">
                  {formatDateTime(o.placed_at)} · {o.items.reduce((n, i) => n + i.quantity, 0)} item(s) ·{" "}
                  {formatPaise(o.payable_paise)}
                </p>
              </div>
              <span className="flex flex-wrap items-center gap-2">
                {o.is_test_fixture ? <TestBadge label="Test order" /> : null}
                <StatusBadge tone={tone(o.fulfilment_status)} label={o.status_label} />
                {o.agent_assigned ? <StatusBadge tone="info" label="Agent Assigned" /> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function OrderPage() {
  const { orderId = "" } = useParams();
  const order = useOrder(orderId);
  const state = queryState(order, { loading: "Loading order…", notFound: "Order not found" });
  if (state) return state;
  if (!order.data) return null;
  const o = order.data;

  return (
    <section className="mx-auto max-w-4xl">
      <p className="text-sm">
        <Link to="/customer/orders" className="underline">
          My Orders
        </Link>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">Order {o.id.slice(0, 8)}</h1>
        <span data-testid="order-status">
          <StatusBadge tone={tone(o.fulfilment_status)} label={o.status_label} />
        </span>
        {o.agent_assigned ? <StatusBadge tone="info" label="Agent Assigned" /> : null}
        {o.is_test_fixture ? <TestBadge label="Test order" /> : null}
      </div>
      <p className="mt-1 text-sm text-text-muted">Placed {formatDateTime(o.placed_at)}</p>
      <Tracking order={o} />
      <PaymentSimulator order={o} />
      <CancelOrder order={o} />
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <section aria-labelledby="items">
          <h2 id="items" className="text-lg font-semibold">
            Items
          </h2>
          <ul className="mt-2 divide-y divide-border rounded-panel border border-border bg-surface text-sm">
            {o.items.map((i) => (
              <li key={i.menu_item_id} className="flex justify-between gap-2 p-3">
                <span>
                  {i.quantity} × {i.item_name}
                </span>
                <span>{formatPaise((i.unit_price_paise ?? 0) * i.quantity)}</span>
              </li>
            ))}
          </ul>
          {o.special_instructions ? (
            <p className="mt-2 text-sm">Instructions: {o.special_instructions}</p>
          ) : null}
        </section>
        <section aria-labelledby="summary">
          <h2 id="summary" className="text-lg font-semibold">
            Bill and delivery
          </h2>
          <dl className="mt-2 space-y-1 rounded-panel border border-border bg-surface p-3 text-sm">
            <Row term="Food subtotal" value={formatPaise(o.food_subtotal_paise)} />
            <Row term="Delivery fee" value={formatPaise(o.delivery_fee_paise)} />
            {o.discount_paise ? <Row term="Coupon" value={`− ${formatPaise(o.discount_paise)}`} /> : null}
            <Row term="Total" value={formatPaise(o.payable_paise)} />
            <Row
              term="Payment"
              value={
                o.payment
                  ? `${PAYMENT_LABELS[o.payment.method] ?? o.payment.method}: ${humanize(o.payment.status)}`
                  : "—"
              }
            />
            <Row term="Deliver to" value={o.delivery_address ?? "—"} />
          </dl>
          <p className="mt-1 text-xs text-text-muted">
            Prices include applicable taxes.{o.road_km_estimated ? " Road distance was estimated." : ""}
          </p>
        </section>
      </div>
    </section>
  );
}

// DDR-113 (6), (8): only on the customer's own order, after pickup. The code is never shown to the agent.
function Tracking({ order }: { order: Order }) {
  if (order.fulfilment_status !== "OUT_FOR_DELIVERY") return null;
  const where = order.live_location;
  return (
    <section
      aria-labelledby="tracking"
      className="mt-4 space-y-2 rounded-panel border border-border bg-surface p-4"
    >
      <h2 id="tracking" className="text-lg font-semibold">
        On the way
      </h2>
      {order.delivery_code ? (
        <p>
          Give this code to the agent:{" "}
          <span className="font-mono text-2xl font-semibold tracking-widest" data-testid="delivery-code">
            {order.delivery_code}
          </span>
        </p>
      ) : null}
      <p className="flex flex-wrap items-center gap-2 text-sm">
        {where ? (
          <>
            Agent last seen at {where.lat.toFixed(4)}, {where.lng.toFixed(4)} (
            {formatDateTime(where.recorded_at)}){where.simulated ? <TestBadge label="Simulated GPS" /> : null}
          </>
        ) : (
          "The agent's position is not available yet."
        )}
      </p>
      <TrackingNote />
    </section>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-text-muted">{term}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

// Labelled simulator step for prepaid orders (DDR-109): never presented as a real gateway.
function PaymentSimulator({ order }: { order: Order }) {
  const simulate = useSimulatePayment(order.id);
  const [error, setError] = useState<string | null>(null);
  if (order.fulfilment_status !== "PLACED" || !order.payment || order.payment.method === "COD") return null;

  async function run(outcome: SimOutcome) {
    setError(null);
    try {
      await simulate.mutateAsync(outcome);
    } catch (e) {
      setError(e instanceof Refusal ? e.message : "Something went wrong. Try again.");
    }
  }

  return (
    <section
      aria-labelledby="simulator"
      className="mt-4 rounded-panel border border-status-warning bg-surface p-4 text-sm"
    >
      <h2 id="simulator" className="text-lg font-semibold">
        Payment simulator
      </h2>
      <p className="mt-1">
        {PAYMENT_LABELS[order.payment.method]} · {formatPaise(order.payment.amount_paise)} · reference{" "}
        {order.payment.sim_reference}
      </p>
      <p className="mt-1 text-text-muted">
        This is a simulation: no real money moves. Choose the result to continue. A failed or timed-out
        payment cancels the order.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => run("SUCCESS")} disabled={simulate.isPending}>
          Simulate success
        </Button>
        <Button variant="secondary" onClick={() => run("FAILED")} disabled={simulate.isPending}>
          Simulate failure
        </Button>
        <Button variant="secondary" onClick={() => run("TIMEOUT")} disabled={simulate.isPending}>
          Simulate timeout
        </Button>
      </div>
      {error ? (
        <p role="alert" className="mt-2">
          {error}
        </p>
      ) : null}
    </section>
  );
}

// CU-19: cancellation only before kitchen acceptance; prepaid is refunded in full (DDR-109).
function CancelOrder({ order }: { order: Order }) {
  const cancel = useCancelOrder(order.id);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (order.fulfilment_status !== "PENDING_KITCHEN") return null;
  const prepaid = order.payment && order.payment.method !== "COD";

  return (
    <div className="mt-4 text-sm">
      {confirming ? (
        <div className="rounded-panel border border-border bg-surface p-3">
          <p>
            Cancel this order?{prepaid ? " The simulated payment is refunded in full." : ""} You can cancel
            only until the kitchen accepts it.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button
              onClick={async () => {
                setError(null);
                try {
                  await cancel.mutateAsync();
                } catch (e) {
                  setError(e instanceof Refusal ? e.message : "Something went wrong. Try again.");
                }
                setConfirming(false);
              }}
              disabled={cancel.isPending}
            >
              Confirm cancellation
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Keep order
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" onClick={() => setConfirming(true)}>
          Cancel order
        </Button>
      )}
      {error ? (
        <p role="alert" className="mt-2">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** DDR-115 (8), (9): the position updates live, or every 10 s while live updates are paused. */
function TrackingNote() {
  const status = useRealtimeStatus();
  return (
    <p className="text-xs text-text-muted" data-testid="tracking-note">
      {status === "live" ? "Updates live." : "Live updates paused · updates every 10 s."}
    </p>
  );
}
