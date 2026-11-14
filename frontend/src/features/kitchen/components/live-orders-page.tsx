import { useState } from "react";

import { useKitchenAction, useKitchenQueue, type KitchenOrder } from "../api";
import { refusalText } from "../format";
import { AgentNote, OrderCard } from "./order-card";
import { IntakeSummary } from "./overview-page";
import { Button } from "@/shared/ui/button";
import { PollNote } from "@/shared/ui/poll-note";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { EmptyState } from "@/shared/ui/states";

// KI-01–KI-03, DDR-112 (1): intake. Incoming by queue entry; held orders FIFO by acceptance (read-only).
export function LiveOrdersPage() {
  const queue = useKitchenQueue();
  const state = queryState(queue, { loading: "Loading orders…" });
  if (state) return state;
  if (!queue.data) return null;
  const q = queue.data;
  const now = queue.dataUpdatedAt;

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Live Orders</h1>
          <PollNote updatedAt={now} />
        </div>
        <IntakeSummary queue={q} />
      </header>
      <section aria-labelledby="incoming">
        <h2 id="incoming" className="text-xl font-semibold">
          Incoming ({q.incoming.length})
        </h2>
        {q.acceptance_timeout_minutes ? (
          <p className="text-xs text-text-muted">
            Orders waiting more than {q.acceptance_timeout_minutes} min are marked Overdue (test default, not
            final). Warnings never change the order.
          </p>
        ) : null}
        {q.incoming.length === 0 ? (
          <EmptyState title="No incoming orders" />
        ) : (
          <div className="mt-3 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            {q.incoming.map((o) => (
              <OrderCard key={o.id} order={o} now={now}>
                {q.can_process ? <IncomingActions order={o} /> : null}
              </OrderCard>
            ))}
          </div>
        )}
      </section>
      <section aria-labelledby="held">
        <h2 id="held" className="text-xl font-semibold">
          In the kitchen ({q.held.length}) · first accepted first
        </h2>
        <AgentNote />
        {q.held.length === 0 ? (
          <EmptyState title="No accepted orders" />
        ) : (
          <ol
            className="mt-3 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3"
            aria-label="Accepted orders in FIFO order"
          >
            {q.held.map((o) => (
              <li key={o.id}>
                <OrderCard order={o} now={now} />
              </li>
            ))}
          </ol>
        )}
      </section>
    </section>
  );
}

function IncomingActions({ order }: { order: KitchenOrder }) {
  const action = useKitchenAction();
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function accept() {
    setError(null);
    try {
      await action.mutateAsync({ kind: "accept", orderId: order.id });
    } catch (e) {
      setError(refusalText(e));
    }
  }

  return (
    <div className="mt-3">
      {rejecting ? (
        <ReasonForm
          label="Why is this order rejected?"
          confirmLabel="Reject order"
          hint="Recorded with your name; a prepaid order is refunded in full."
          onCancel={() => setRejecting(false)}
          onConfirm={async (reason) => {
            try {
              await action.mutateAsync({ kind: "reject", orderId: order.id, reason });
            } catch (e) {
              throw new Error(refusalText(e), { cause: e });
            }
          }}
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button onClick={accept} disabled={action.isPending}>
            Accept
          </Button>
          <Button variant="secondary" onClick={() => setRejecting(true)} disabled={action.isPending}>
            Reject
          </Button>
        </div>
      )}
      {error ? (
        <p role="alert" className="mt-2 rounded-control border border-status-danger p-2 text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}
