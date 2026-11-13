import { Link } from "react-router";

import { useKitchenQueue, useLowStock } from "../api";
import { formatQty } from "../format";
import { OrderCard } from "./order-card";
import { PollNote } from "@/shared/ui/poll-note";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { TestBadge } from "@/shared/ui/test-badge";

// DDR-111 (12): overdue Incoming orders and low stock only. Delay/ETA records are not part of Task 8.
export function ExceptionsPage() {
  const queue = useKitchenQueue();
  const low = useLowStock();
  const state = queryState(queue, { loading: "Loading exceptions…" });
  if (state) return state;
  if (!queue.data) return null;
  const overdue = queue.data.incoming.filter((o) => o.overdue);

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Exceptions</h1>
        <PollNote updatedAt={queue.dataUpdatedAt} />
      </header>
      <section aria-labelledby="overdue">
        <h2 id="overdue" className="text-xl font-semibold">
          Overdue incoming orders ({overdue.length})
        </h2>
        {overdue.length === 0 ? (
          <EmptyState title="No overdue orders" />
        ) : (
          <div className="mt-3 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            {overdue.map((o) => (
              <OrderCard key={o.id} order={o} now={queue.dataUpdatedAt}>
                <Link to="/kitchen/live-orders" className="mt-2 inline-block text-sm underline">
                  Accept or reject in Live Orders
                </Link>
              </OrderCard>
            ))}
          </div>
        )}
      </section>
      <section aria-labelledby="low">
        <h2 id="low" className="text-xl font-semibold">
          Low stock ({low.data?.length ?? 0})
        </h2>
        {queryState(low, { loading: "Loading stock alerts…" }) ??
          (low.data && low.data.length > 0 ? (
            <ul className="mt-3 space-y-2">
              {low.data.map((s) => (
                <li
                  key={s.ingredient_id}
                  className="rounded-panel border border-border bg-surface p-3 text-sm"
                >
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {s.name} {s.is_test_fixture ? <TestBadge label="Test stock" /> : null}
                  </p>
                  <p>
                    {formatQty(s.available, s.unit)} available · threshold{" "}
                    {formatQty(s.low_stock_threshold, s.unit)}
                    {s.used_in.length ? ` · used in ${s.used_in.join(", ")}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No low-stock alerts">
              Alerts appear when stock reaches a threshold the Kitchen Manager set.
            </EmptyState>
          ))}
      </section>
    </section>
  );
}
