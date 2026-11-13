import { useEffect, type ReactNode } from "react";
import { Link } from "react-router";
import { WifiOff } from "lucide-react";

import { useMyWork, type MyWork, type WorkOrder } from "../api";
import { start, stop, useGps, type Mode } from "../tracker";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatPaise } from "@/shared/utils/format";

const HELD = ["ACCEPTED", "FAILURE_REQUESTED"];

export function isHeld(work: MyWork | undefined): boolean {
  return Boolean(work?.assignment && HELD.includes(work.assignment.status));
}

/** Keeps the GPS session in step with the open delivery (DDR-113 (20)): on while held, off otherwise. */
function GpsSession({ work }: { work: MyWork | undefined }) {
  const gps = useGps();
  const held = isHeld(work);
  const order = work?.order;
  const moving = order?.fulfilment_status === "OUT_FOR_DELIVERY";
  useEffect(() => {
    if (!held || !order) {
      if (gps.mode) stop();
      return;
    }
    if (gps.mode) start(gps.mode, { from: order.kitchen, to: order.destination, moving });
  }, [held, order, moving, gps.mode]);
  return null;
}

/** Every Delivery page: the offline banner and the GPS session. */
export function DeliveryPage({ title, children }: { title: string; children: (work: MyWork) => ReactNode }) {
  const work = useMyWork();
  const gps = useGps();
  const state = queryState(work, { loading: "Loading your deliveries…" });
  return (
    <section className="mx-auto max-w-xl space-y-4">
      <GpsSession work={work.data} />
      <h1 className="text-2xl font-semibold">{title}</h1>
      {!gps.online ? (
        <p
          role="alert"
          className="flex items-center gap-2 rounded-panel border border-status-danger bg-surface p-3 text-sm"
        >
          <WifiOff className="size-5" aria-hidden="true" /> You are offline. Location points are kept and
          re-sent on reconnect; pickup, code entry and other actions wait until you are back online.
        </p>
      ) : null}
      {state ?? (work.data ? children(work.data) : null)}
    </section>
  );
}

export function NoDelivery() {
  return (
    <EmptyState title="No active delivery">
      <Link to="/delivery" className="underline">
        Go online on Home to receive offers
      </Link>
    </EmptyState>
  );
}

const PAYMENT: Record<string, string> = {
  COD: "Cash on Delivery",
  SIM_UPI: "Prepaid (UPI, simulated)",
  SIM_CARD: "Prepaid (card, simulated)",
};

/** DL-08: order ID, items, instructions; the address once accepted; the masked phone. */
export function OrderSummary({ order, accepted }: { order: WorkOrder; accepted: boolean }) {
  return (
    <div
      className="space-y-2 rounded-panel border border-border bg-surface p-4 text-sm"
      data-testid="delivery-order"
    >
      <p className="flex flex-wrap items-center gap-2">
        <span className="text-lg font-semibold">Order {order.order_id.slice(0, 8)}</span>
        {order.is_test_fixture ? <TestBadge label="Test order" /> : null}
        <StatusBadge tone="info" label={order.status_label} />
      </p>
      <ul aria-label="Items">
        {order.items.map((i) => (
          <li key={i.name}>
            {i.quantity} × {i.name}
          </li>
        ))}
      </ul>
      <p>
        Pick up at {order.kitchen_name}
        {order.kitchen_location_is_synthetic ? " (synthetic test location)" : ""}
      </p>
      {accepted ? (
        <>
          <p>
            <span className="font-medium">Deliver to:</span> {order.delivery_address ?? "—"}
          </p>
          {order.special_instructions ? <p>Instructions: {order.special_instructions}</p> : null}
        </>
      ) : (
        <p className="text-text-muted">The address is shown after you accept.</p>
      )}
      <p>
        Customer: {order.customer_phone_masked} ·{" "}
        {order.payment_method ? (PAYMENT[order.payment_method] ?? order.payment_method) : "—"}
        {order.payment_method === "COD" ? ` · collect ${formatPaise(order.payable_paise)}` : ""}
      </p>
      {order.delivery_exception_open ? (
        <p role="status" className="font-medium">
          The manager has been alerted about this delivery.
        </p>
      ) : null}
    </div>
  );
}

const GPS_TEXT: Record<string, string> = {
  idle: "Location is not being shared.",
  waiting: "Waiting for your location…",
  ok: "Location is being shared.",
  denied: "Location access was denied. Allow it in the browser settings, or use simulated GPS for a demo.",
  unavailable: "Your location is unavailable right now. No position is sent until it returns.",
};

/** DL-G2, DL-G3: real or simulated GPS, clearly labelled; honest warnings; foreground only. */
export function GpsPanel() {
  const gps = useGps();
  const choose = (mode: Mode) => start(mode, { from: { lat: 0, lng: 0 }, to: null, moving: false });
  return (
    <section
      aria-labelledby="gps"
      className="space-y-2 rounded-panel border border-border bg-surface p-4 text-sm"
    >
      <h2 id="gps" className="flex flex-wrap items-center gap-2 font-semibold">
        Location sharing
        {gps.mode === "SIMULATED" ? <TestBadge label="Simulated GPS" /> : null}
        {gps.mode === "REAL" ? <StatusBadge tone="info" label="Real GPS" /> : null}
      </h2>
      <p role={gps.status === "denied" || gps.status === "unavailable" ? "alert" : undefined}>
        {GPS_TEXT[gps.status]}
      </p>
      {gps.accuracyM !== null && gps.mode === "REAL" ? (
        <p>Accuracy about {Math.round(gps.accuracyM)} m.</p>
      ) : null}
      <p className="text-text-muted">
        Keep this app open while delivering: location is not shared in the background.
        {gps.buffered ? ` ${gps.buffered} point(s) waiting to send.` : ""}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant={gps.mode === "REAL" ? "primary" : "secondary"} onClick={() => choose("REAL")}>
          Use real GPS
        </Button>
        <Button
          variant={gps.mode === "SIMULATED" ? "primary" : "secondary"}
          onClick={() => choose("SIMULATED")}
        >
          Use simulated GPS
        </Button>
      </div>
      {gps.mode === "SIMULATED" ? (
        <p className="text-xs text-text-muted">
          Simulation: 15 m every 5 s along a straight line (not a real position).
        </p>
      ) : null}
    </section>
  );
}
