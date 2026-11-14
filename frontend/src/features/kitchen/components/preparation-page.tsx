import { useState } from "react";

import { useKitchenAction, useKitchenQueue, type KitchenItem, type KitchenOrder } from "../api";
import { refusalText } from "../format";
import { AgentNote, OrderCard } from "./order-card";
import { Button } from "@/shared/ui/button";
import { PollNote } from "@/shared/ui/poll-note";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { EmptyState } from "@/shared/ui/states";

const COLUMNS: { status: KitchenOrder["fulfilment_status"]; title: string }[] = [
  { status: "ACCEPTED", title: "Accepted" },
  { status: "PREPARING", title: "Preparing" },
  { status: "READY_FOR_PICKUP", title: "Ready for Pickup" },
];

// KI-04–KI-06, DDR-112 (1): the work. Three columns at KDS widths; FIFO inside each column.
export function PreparationPage() {
  const queue = useKitchenQueue();
  const state = queryState(queue, { loading: "Loading the board…" });
  if (state) return state;
  if (!queue.data) return null;
  const q = queue.data;

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Preparation Board</h1>
        <PollNote updatedAt={queue.dataUpdatedAt} />
        <AgentNote />
      </header>
      {q.held.length === 0 ? (
        <EmptyState title="Nothing to prepare">Accepted orders appear here, first accepted first.</EmptyState>
      ) : (
        <div className="grid gap-4 2xl:grid-cols-3">
          {COLUMNS.map((c) => {
            const orders = q.held.filter((o) => o.fulfilment_status === c.status);
            return (
              <section key={c.status} aria-labelledby={`col-${c.status}`} className="space-y-3">
                <h2 id={`col-${c.status}`} className="text-lg font-semibold">
                  {c.title} ({orders.length})
                </h2>
                {orders.map((o) => (
                  <OrderCard key={o.id} order={o} now={queue.dataUpdatedAt}>
                    <PrepControls
                      order={o}
                      canProcess={q.can_process}
                      canRejectAccepted={q.can_reject_accepted}
                    />
                  </OrderCard>
                ))}
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}

function PrepControls({
  order,
  canProcess,
  canRejectAccepted,
}: {
  order: KitchenOrder;
  canProcess: boolean;
  canRejectAccepted: boolean;
}) {
  const action = useKitchenAction();
  const [error, setError] = useState<string | null>(null);
  const [cannotFulfil, setCannotFulfil] = useState(false);
  const editable = order.fulfilment_status === "ACCEPTED" || order.fulfilment_status === "PREPARING";

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(refusalText(e));
    }
  }

  return (
    <div className="mt-3 space-y-2">
      {canProcess && editable ? (
        <>
          {order.items.some((i) => i.prep_status === "PENDING") ? (
            <Button
              onClick={() => run(() => action.mutateAsync({ kind: "start", orderId: order.id }))}
              disabled={action.isPending}
            >
              Start order
            </Button>
          ) : null}
          <ul className="space-y-2" aria-label="Item steps">
            {order.items.map((item) => (
              <ItemRow
                key={item.id}
                item={item}
                busy={action.isPending}
                onStep={(status) =>
                  run(() => action.mutateAsync({ kind: "item", orderId: order.id, itemId: item.id, status }))
                }
              />
            ))}
          </ul>
        </>
      ) : null}
      {order.fulfilment_status === "READY_FOR_PICKUP" ? (
        <p className="text-sm">Ready: the agent's validated pickup hands it over (KI-08).</p>
      ) : null}
      {canRejectAccepted ? (
        cannotFulfil ? (
          <ReasonForm
            label="Why can this order not be fulfilled?"
            confirmLabel="Reject order"
            hint="Releases reserved stock, refunds a prepaid order in full and withdraws the agent offer."
            onCancel={() => setCannotFulfil(false)}
            onConfirm={async (reason) => {
              try {
                await action.mutateAsync({ kind: "reject", orderId: order.id, reason });
              } catch (e) {
                throw new Error(refusalText(e), { cause: e });
              }
            }}
          />
        ) : (
          <Button variant="ghost" onClick={() => setCannotFulfil(true)}>
            Cannot fulfil
          </Button>
        )
      ) : null}
      {error ? (
        <p role="alert" className="rounded-control border border-status-danger p-2 text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}

const NEXT: Record<string, { status: "PREPARING" | "PREPARED"; label: string } | undefined> = {
  PENDING: { status: "PREPARING", label: "Preparing" },
  PREPARING: { status: "PREPARED", label: "Prepared" },
};
const ITEM_LABEL: Record<string, string> = {
  PENDING: "Pending",
  PREPARING: "Preparing",
  PREPARED: "Prepared",
};

function ItemRow({
  item,
  busy,
  onStep,
}: {
  item: KitchenItem;
  busy: boolean;
  onStep: (status: "PREPARING" | "PREPARED") => void;
}) {
  const next = NEXT[item.prep_status];
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-control bg-muted p-2 text-sm">
      <span>
        {item.quantity} × {item.item_name} ·{" "}
        <span className="font-medium">{ITEM_LABEL[item.prep_status]}</span>
      </span>
      {next ? (
        <Button
          variant="secondary"
          onClick={() => onStep(next.status)}
          disabled={busy}
          aria-label={`Mark ${item.item_name ?? "item"} ${next.label}`}
        >
          {next.label}
        </Button>
      ) : null}
    </li>
  );
}
