import { useId, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { csvHref, ORDER_STATUSES, useAgents, useKitchens, useOrders, type OrderFilters } from "../api";
import { dayBound, PageHeader, Pager, TableBox, Td, Th } from "./common";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, formatPaise, humanize } from "@/shared/utils/format";

type Form = { status: string; kitchen: string; agent: string; exception: boolean; from: string; to: string };

function toFilters(f: Form): OrderFilters {
  return {
    status: f.status || undefined,
    kitchen_id: f.kitchen || undefined,
    agent_id: f.agent || undefined,
    exception: f.exception ? true : undefined,
    date_from: dayBound(f.from, false),
    date_to: dayBound(f.to, true),
  };
}

// DDR-114 (9): filters status, date (≤ 31 days, default last 7), kitchen, agent, exception flag; 50 per
// page; the CSV export is the current filtered view, same scope, ≤ 5,000 rows, audited (DDR-114 (8)).
export function OrdersPage() {
  const [params] = useSearchParams();
  const initial: Form = {
    status: params.get("status") ?? "",
    kitchen: "",
    agent: "",
    exception: params.get("exception") === "true",
    from: "",
    to: "",
  };
  const [form, setForm] = useState<Form>(initial);
  const [applied, setApplied] = useState<OrderFilters>(toFilters(initial));
  const [page, setPage] = useState(1);
  const orders = useOrders(page, applied);
  const kitchens = useKitchens();
  const agents = useAgents();
  const id = useId();

  function apply(event: FormEvent) {
    event.preventDefault();
    setApplied(toFilters(form));
    setPage(1);
  }

  const state = queryState(orders, { loading: "Loading orders…" });
  return (
    <section className="mx-auto max-w-6xl space-y-4">
      <PageHeader title="Orders & Exceptions" updatedAt={orders.dataUpdatedAt} />
      <form
        onSubmit={apply}
        className="grid gap-3 rounded-panel border border-border bg-surface p-3 sm:grid-cols-3 lg:grid-cols-6"
        aria-label="Order filters"
      >
        <div>
          <label htmlFor={`${id}-status`} className="block text-sm font-medium">
            Status
          </label>
          <select
            id={`${id}-status`}
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          >
            <option value="">Any</option>
            {ORDER_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
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
            <option value="">Any</option>
            {(kitchens.data ?? []).map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-agent`} className="block text-sm font-medium">
            Agent
          </label>
          <select
            id={`${id}-agent`}
            value={form.agent}
            onChange={(e) => setForm({ ...form, agent: e.target.value })}
            className={`mt-1 w-full ${INPUT}`}
          >
            <option value="">Any</option>
            {(agents.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
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
        <label className="flex min-h-11 items-center gap-2 self-end text-sm">
          <input
            type="checkbox"
            className="size-5"
            checked={form.exception}
            onChange={(e) => setForm({ ...form, exception: e.target.checked })}
          />
          Exception open only
        </label>
        <p className="text-xs text-text-muted sm:col-span-3 lg:col-span-4">
          Without dates the last 7 days are shown; a range can be at most 31 days.
        </p>
        <div className="flex flex-wrap gap-2 sm:col-span-3 lg:col-span-2 lg:justify-end">
          <Button type="submit">Apply filters</Button>
          <Button asChild variant="secondary">
            <a href={csvHref("orders.csv", applied)} download>
              Export CSV
            </a>
          </Button>
        </div>
      </form>

      {state ??
        (orders.data && orders.data.rows.length > 0 ? (
          <>
            <TableBox label="Orders">
              <thead className="bg-muted">
                <tr>
                  <Th>Order</Th>
                  <Th>Placed</Th>
                  <Th>Status</Th>
                  <Th>Kitchen</Th>
                  <Th>Payment</Th>
                  <Th>Agent</Th>
                </tr>
              </thead>
              <tbody>
                {orders.data.rows.map((o) => (
                  <tr key={o.id} className="border-t border-border">
                    <Td>
                      <Link to={`/management/orders/${o.id}`} className="underline">
                        {o.id.slice(0, 8)}
                      </Link>
                      <span className="mt-1 flex flex-wrap gap-1">
                        {o.is_test_fixture ? <TestBadge label="Test order" /> : null}
                        {o.delivery_exception_open ? (
                          <StatusBadge tone="danger" label="Exception open" />
                        ) : null}
                      </span>
                    </Td>
                    <Td>{formatDateTime(o.placed_at)}</Td>
                    <Td>{o.status_label}</Td>
                    <Td>{o.kitchen_name}</Td>
                    <Td>
                      {formatPaise(o.payable_paise)}
                      <span className="block text-xs text-text-muted">
                        {o.payment_method ?? "—"} · {o.payment_status ? humanize(o.payment_status) : "—"}
                      </span>
                    </Td>
                    <Td>
                      {o.agent_name ?? "—"}
                      {o.assignment_status ? (
                        <span className="block text-xs text-text-muted">{humanize(o.assignment_status)}</span>
                      ) : null}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </TableBox>
            <Pager
              page={orders.data.page}
              pageSize={orders.data.page_size}
              total={orders.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <p className="text-sm">No orders match these filters in your scope.</p>
        ))}
    </section>
  );
}
