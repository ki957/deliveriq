import { useEffect, useState } from "react";
import { Link } from "react-router";

import {
  refusalText,
  revealPhone,
  useCod,
  useContactManager,
  useCustomerUnavailable,
  useDeliver,
  useFailureRequest,
  usePickup,
  useRespond,
  useSetAvailability,
  type MyWork,
} from "../api";
import { useGps } from "../tracker";
import { DeliveryPage, GpsPanel, isHeld, NoDelivery, OrderSummary } from "./shared";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { ReasonForm } from "@/shared/ui/reason-form";
import { StatusBadge } from "@/shared/ui/status-badge";

function Alert({ text }: { text: string | null }) {
  return text ? (
    <p role="alert" className="rounded-control border border-status-danger p-2 text-sm">
      {text}
    </p>
  ) : null;
}

function useOnline(): boolean {
  return useGps().online;
}

// ---------------------------------------------------------------- Home (DL-01, DL-04)
function useSecondsLeft(work: MyWork, updatedAt: number): number | null {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(id);
  }, []);
  const left = work.assignment?.offer_seconds_left;
  if (left === null || left === undefined) return null;
  return Math.max(0, left - Math.floor((now - updatedAt) / 1000));
}

export function DeliveryHomePage() {
  return <DeliveryPage title="Home">{(work) => <Home work={work} />}</DeliveryPage>;
}

function Home({ work }: { work: MyWork }) {
  const availability = useSetAvailability();
  const [error, setError] = useState<string | null>(null);
  const online = work.availability === "ONLINE";
  const held = isHeld(work);
  const offered = work.assignment?.status === "OFFERED";

  async function toggle() {
    setError(null);
    try {
      await availability.mutateAsync(!online);
    } catch (e) {
      setError(refusalText(e));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-panel border border-border bg-surface p-4">
        <StatusBadge
          tone={online ? "success" : "neutral"}
          label={online ? "Online: receiving offers" : "Offline"}
        />
        <Button onClick={toggle} disabled={availability.isPending} variant={online ? "secondary" : "primary"}>
          {online ? "Go offline" : "Go online"}
        </Button>
      </div>
      <Alert text={error} />
      {offered && work.order ? <Offer work={work} /> : null}
      {held && work.order ? (
        <div className="space-y-3">
          <OrderSummary order={work.order} accepted />
          <NextStep work={work} />
        </div>
      ) : null}
      {!work.assignment ? (
        <p className="text-sm text-text-muted">
          {online
            ? "Waiting for an offer. You have 60 seconds to answer each one."
            : "Go online to receive offers."}
        </p>
      ) : null}
    </div>
  );
}

function Offer({ work }: { work: MyWork }) {
  const respond = useRespond();
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt] = useState(Date.now);
  const left = useSecondsLeft(work, updatedAt);
  const id = work.assignment?.id ?? "";
  if (!work.order) return null;

  async function accept() {
    setError(null);
    try {
      await respond.mutateAsync({ id, accept: true });
    } catch (e) {
      setError(refusalText(e));
    }
  }

  return (
    <section
      aria-labelledby="offer"
      className="space-y-3 rounded-panel border-2 border-status-warning bg-surface p-4"
    >
      <h2 id="offer" className="text-xl font-semibold">
        New delivery offer
      </h2>
      <p aria-live="polite" data-testid="offer-countdown">
        {left === null ? "" : `${left} s left to answer`}
      </p>
      <OrderSummary order={work.order} accepted={false} />
      {rejecting ? (
        <ReasonForm
          label="Why are you rejecting this offer?"
          confirmLabel="Reject offer"
          minLength={1}
          onCancel={() => setRejecting(false)}
          onConfirm={async (reason) => {
            try {
              await respond.mutateAsync({ id, accept: false, reason });
            } catch (e) {
              throw new Error(refusalText(e), { cause: e });
            }
          }}
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button onClick={accept} disabled={respond.isPending}>
            Accept
          </Button>
          <Button variant="secondary" onClick={() => setRejecting(true)} disabled={respond.isPending}>
            Reject
          </Button>
        </div>
      )}
      <Alert text={error} />
    </section>
  );
}

function NextStep({ work }: { work: MyWork }) {
  const status = work.order?.fulfilment_status;
  const failure = work.assignment?.status === "FAILURE_REQUESTED";
  const [to, label] = failure
    ? ["/delivery/exceptions", "A failure request is waiting for the manager"]
    : status === "READY_FOR_PICKUP"
      ? ["/delivery/pickup", "The order is ready: go to Pickup"]
      : status === "OUT_FOR_DELIVERY"
        ? ["/delivery/completion", "On the way: enter the customer's code at the door"]
        : ["/delivery/active", "Go to the kitchen; the order is being prepared"];
  return (
    <Link
      to={to}
      className="block rounded-panel bg-primary p-4 text-center font-semibold text-primary-foreground"
    >
      {label}
    </Link>
  );
}

// ---------------------------------------------------------------- Assignment and Active delivery (DL-08)
export function AssignmentPage() {
  return (
    <DeliveryPage title="Assignment">
      {(work) =>
        work.order && work.assignment ? (
          <OrderSummary order={work.order} accepted={isHeld(work)} />
        ) : (
          <NoDelivery />
        )
      }
    </DeliveryPage>
  );
}

export function ActiveDeliveryPage() {
  return (
    <DeliveryPage title="Active delivery">
      {(work) => (isHeld(work) && work.order ? <Active work={work} /> : <NoDelivery />)}
    </DeliveryPage>
  );
}

function Active({ work }: { work: MyWork }) {
  const [phone, setPhone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contacting, setContacting] = useState(false);
  const contact = useContactManager();
  const online = useOnline();
  const order = work.order;
  if (!order) return null;

  return (
    <div className="space-y-4">
      <OrderSummary order={order} accepted />
      <NextStep work={work} />
      <GpsPanel />
      <div className="flex flex-wrap gap-2">
        {phone ? (
          <a href={`tel:${phone}`} className="underline">
            Call {phone}
          </a>
        ) : (
          <Button
            variant="secondary"
            disabled={!online}
            onClick={async () => {
              setError(null);
              try {
                setPhone(await revealPhone(order.order_id));
              } catch (e) {
                setError(refusalText(e));
              }
            }}
          >
            Show customer number
          </Button>
        )}
        {order.fulfilment_status === "OUT_FOR_DELIVERY" && !contacting ? (
          <Button variant="secondary" onClick={() => setContacting(true)} disabled={!online}>
            Contact manager
          </Button>
        ) : null}
      </div>
      <p className="text-xs text-text-muted">Showing the full number is recorded.</p>
      {contacting ? (
        <ReasonForm
          label="What do you need help with?"
          confirmLabel="Alert the manager"
          minLength={1}
          onCancel={() => setContacting(false)}
          onConfirm={async (reason) => {
            try {
              await contact.mutateAsync({ id: order.order_id, reason });
              setContacting(false);
            } catch (e) {
              throw new Error(refusalText(e), { cause: e });
            }
          }}
        />
      ) : null}
      <Alert text={error} />
    </div>
  );
}

// ---------------------------------------------------------------- Pickup (DL-09)
export function PickupPage() {
  return (
    <DeliveryPage title="Pickup">
      {(work) => (isHeld(work) && work.order ? <Pickup work={work} /> : <NoDelivery />)}
    </DeliveryPage>
  );
}

function Pickup({ work }: { work: MyWork }) {
  const pickup = usePickup();
  const online = useOnline();
  const [error, setError] = useState<string | null>(null);
  const order = work.order;
  if (!order) return null;
  const ready = order.fulfilment_status === "READY_FOR_PICKUP";
  if (order.fulfilment_status === "OUT_FOR_DELIVERY") {
    return (
      <p role="status">
        Picked up.{" "}
        <Link to="/delivery/completion" className="underline">
          Enter the customer's code at the door.
        </Link>
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <OrderSummary order={order} accepted />
      <p>
        {ready
          ? "The order is ready. Check the items, then confirm."
          : "Wait until the kitchen marks the order Ready."}
      </p>
      <Button
        className="w-full"
        disabled={!ready || !online || pickup.isPending}
        onClick={async () => {
          setError(null);
          try {
            await pickup.mutateAsync(order.order_id);
          } catch (e) {
            setError(refusalText(e));
          }
        }}
      >
        Picked up
      </Button>
      <Alert text={error} />
    </div>
  );
}

// ---------------------------------------------------------------- Completion (DL-11, DL-15)
export function CompletionPage() {
  return (
    <DeliveryPage title="Completion">
      {(work) => (isHeld(work) && work.order ? <Completion work={work} /> : <NoDelivery />)}
    </DeliveryPage>
  );
}

function Completion({ work }: { work: MyWork }) {
  const deliver = useDeliver();
  const cod = useCod();
  const online = useOnline();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mismatch, setMismatch] = useState(false);
  const order = work.order;
  if (!order) return null;
  if (order.fulfilment_status !== "OUT_FOR_DELIVERY") {
    return <p>The code is entered at the customer's door, after pickup.</p>;
  }
  const locked = order.code_attempts_left === 0;
  const isCod = order.payment_method === "COD";

  return (
    <div className="space-y-4">
      <OrderSummary order={order} accepted />
      {isCod ? (
        <section
          aria-labelledby="cod"
          className="space-y-2 rounded-panel border border-border bg-surface p-4 text-sm"
        >
          <h2 id="cod" className="font-semibold">
            Cash on Delivery (simulated)
          </h2>
          <p>Payment status: {order.payment_status ?? "—"}</p>
          {order.payment_status === "COLLECTION_PENDING" ? (
            mismatch ? (
              <ReasonForm
                label="What was different about the payment?"
                confirmLabel="Report mismatch"
                minLength={1}
                onCancel={() => setMismatch(false)}
                onConfirm={async (reason) => {
                  try {
                    await cod.mutateAsync({ id: order.order_id, collected: false, reason });
                  } catch (e) {
                    throw new Error(refusalText(e), { cause: e });
                  }
                }}
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  disabled={!online || cod.isPending}
                  onClick={() => cod.mutate({ id: order.order_id, collected: true })}
                >
                  Cash collected
                </Button>
                <Button variant="ghost" onClick={() => setMismatch(true)}>
                  Amount mismatch
                </Button>
              </div>
            )
          ) : null}
        </section>
      ) : null}
      <form
        className="space-y-2 rounded-panel border border-border bg-surface p-4"
        noValidate
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          if (!/^\d{6}$/.test(code)) {
            setError("Enter the six-digit code the customer shows you.");
            return;
          }
          try {
            await deliver.mutateAsync({ id: order.order_id, code });
            setCode("");
          } catch (err) {
            setError(refusalText(err));
          }
        }}
      >
        <label htmlFor="delivery-code" className="block font-semibold">
          Customer's delivery code
        </label>
        <input
          id="delivery-code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className={`w-40 text-xl tracking-widest ${INPUT}`}
          disabled={locked}
        />
        <p className="text-sm text-text-muted">
          {locked
            ? "Three wrong codes: the code is locked and the manager has been alerted."
            : `${order.code_attempts_left ?? 3} attempt(s) left. Only the backend can mark the order Delivered.`}
        </p>
        <Button type="submit" disabled={locked || !online || deliver.isPending}>
          Confirm delivery
        </Button>
      </form>
      <Alert text={error} />
    </div>
  );
}

// ---------------------------------------------------------------- Exceptions (#7 §7; DDR-14)
export function DeliveryExceptionsPage() {
  return (
    <DeliveryPage title="Exceptions">
      {(work) => (isHeld(work) && work.order ? <Exceptions work={work} /> : <NoDelivery />)}
    </DeliveryPage>
  );
}

function Exceptions({ work }: { work: MyWork }) {
  const unavailable = useCustomerUnavailable();
  const contact = useContactManager();
  const failure = useFailureRequest();
  const online = useOnline();
  const [now, setNow] = useState(Date.now);
  const [form, setForm] = useState<"refused" | "failed" | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(id);
  }, []);
  const order = work.order;
  if (!order) return null;
  if (work.assignment?.status === "FAILURE_REQUESTED") {
    return <p role="status">Your failure request is waiting for the manager's decision.</p>;
  }
  if (order.fulfilment_status !== "OUT_FOR_DELIVERY") {
    return (
      <p>Exceptions are reported after pickup. Use Contact manager on Active delivery in an emergency.</p>
    );
  }
  const since = order.customer_unavailable_since
    ? new Date(order.customer_unavailable_since).getTime()
    : null;
  const waitMs = work.customer_unavailable_wait_minutes * 60_000;
  const remaining = since === null ? null : Math.max(0, Math.ceil((since + waitMs - now) / 1000));

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(refusalText(e));
    }
  }

  return (
    <div className="space-y-4">
      <section
        aria-labelledby="unavailable"
        className="space-y-2 rounded-panel border border-border bg-surface p-4 text-sm"
      >
        <h2 id="unavailable" className="font-semibold">
          Customer not available
        </h2>
        <p>
          Call the customer, then wait {work.customer_unavailable_wait_minutes} minutes before contacting the
          manager.
        </p>
        {remaining === null ? (
          <Button
            variant="secondary"
            disabled={!online}
            onClick={() => run(() => unavailable.mutateAsync(order.order_id))}
          >
            Start the wait
          </Button>
        ) : remaining > 0 ? (
          <p aria-live="polite" data-testid="wait-timer">
            Waiting: {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")} left
          </p>
        ) : (
          <Button disabled={!online} onClick={() => run(() => contact.mutateAsync({ id: order.order_id }))}>
            Contact manager
          </Button>
        )}
      </section>
      <section
        aria-labelledby="failure"
        className="space-y-2 rounded-panel border border-border bg-surface p-4 text-sm"
      >
        <h2 id="failure" className="font-semibold">
          Cannot deliver
        </h2>
        <p>The manager decides; the order is not marked failed until then.</p>
        {form ? (
          <ReasonForm
            label={
              form === "refused" ? "Why did the customer refuse?" : "Why can the order not be delivered?"
            }
            confirmLabel="Send to manager"
            minLength={1}
            onCancel={() => setForm(null)}
            onConfirm={async (reason) => {
              try {
                await failure.mutateAsync({ id: order.order_id, refused: form === "refused", reason });
                setForm(null);
              } catch (e) {
                throw new Error(refusalText(e), { cause: e });
              }
            }}
          />
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={!online} onClick={() => setForm("refused")}>
              Customer refused
            </Button>
            <Button variant="secondary" disabled={!online} onClick={() => setForm("failed")}>
              Delivery failed
            </Button>
          </div>
        )}
      </section>
      <Alert text={error} />
    </div>
  );
}
