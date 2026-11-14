import { Link } from "react-router";

import { useRefunds } from "../api";
import { PageHeader, TableBox, Td, Th } from "./common";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, formatPaise, humanize } from "@/shared/utils/format";

// DDR-114 (6): read-only refund view (actor, amount, reason, order, outcome; MG-05). Exceptional approval
// and CA override are disabled while no threshold is configured (DDR-44); there is no manual refund.
// Promotions are a labelled placeholder (DDR-114 (2)).
export function PaymentsPage() {
  const refunds = useRefunds();
  const state = queryState(refunds, { loading: "Loading refunds…" });
  if (state) return state;
  const r = refunds.data;
  if (!r) return null;
  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Payments & Promotions" />
      <section aria-labelledby="refunds" className="space-y-2">
        <h2 id="refunds" className="text-lg font-semibold">
          Refunds
        </h2>
        <ul className="space-y-1 text-sm" data-testid="refund-rules">
          <li>
            Exceptional refund approval: <span className="font-medium">{r.disabled_reason}</span>
          </li>
          <li>
            Central Administrator override: <span className="font-medium">{r.disabled_reason}</span>
          </li>
          <li>
            Routine refunds are automatic and in full: a prepaid order cancelled before acceptance or rejected
            by the kitchen (DDR-109). Cash on delivery is never refunded.
          </li>
        </ul>
        {r.rows.length === 0 ? (
          <p className="text-sm">No refunds or pending refund decisions in your scope.</p>
        ) : (
          <TableBox label="Refunds">
            <thead className="bg-muted">
              <tr>
                <Th>Order</Th>
                <Th>Amount</Th>
                <Th>Outcome</Th>
                <Th>By</Th>
                <Th>Reason</Th>
                <Th>When</Th>
              </tr>
            </thead>
            <tbody>
              {r.rows.map((row) => (
                <tr key={row.order_id} className="border-t border-border">
                  <Td>
                    <Link to={`/management/orders/${row.order_id}`} className="underline">
                      {row.order_id.slice(0, 8)}
                    </Link>
                    {row.is_test_fixture ? (
                      <span className="mt-1 block">
                        <TestBadge label="Test order" />
                      </span>
                    ) : null}
                  </Td>
                  <Td>
                    {formatPaise(row.amount_paise)}
                    <span className="block text-xs text-text-muted">{row.method}</span>
                  </Td>
                  <Td>
                    {row.pending_decision ? (
                      <StatusBadge
                        tone="warning"
                        label="Refund decision pending: exceptional refunds disabled"
                      />
                    ) : (
                      humanize(row.status)
                    )}
                  </Td>
                  <Td>{row.actor_name ?? (row.actor_role ? humanize(row.actor_role) : "—")}</Td>
                  <Td>{row.reason ?? "—"}</Td>
                  <Td>{formatDateTime(row.changed_at)}</Td>
                </tr>
              ))}
            </tbody>
          </TableBox>
        )}
      </section>
      <section
        aria-labelledby="promotions"
        className="rounded-panel border border-dashed border-border bg-surface p-4"
      >
        <h2 id="promotions" className="text-lg font-semibold">
          Promotions
        </h2>
        <p className="mt-1 font-medium">Not built yet</p>
        <p className="text-sm text-text-muted">
          Promotion rules (eligibility, dates, limits) are not defined in the sources, so no promotion can be
          created here. Nothing in this section is live.
        </p>
      </section>
    </section>
  );
}
