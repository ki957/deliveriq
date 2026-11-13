import { useId, useState } from "react";
import { Link, useParams } from "react-router";

import {
  useAgents,
  useAssignAgent,
  useCannotFulfil,
  useFailureDecision,
  useOrderDetail,
  useReissueCode,
  type OrderRow,
} from "../api";
import { PageHeader, ReasonAction, TableBox, Td, Th } from "./common";
import { useCan } from "@/shared/auth/require-permission";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, formatPaise, humanize } from "@/shared/utils/format";

const KITCHEN_HOLDS = ["ACCEPTED", "PREPARING", "READY_FOR_PICKUP"];

// DDR-114 (9): fulfilment, payment and assignment timelines with actor and reason; actions go through
// the owning modules' existing APIs, each with a reason (MG-03). The backend re-checks every rule.
export function OrderDetailPage() {
  const { orderId = "" } = useParams();
  const detail = useOrderDetail(orderId);
  const state = queryState(detail, {
    loading: "Loading order…",
    notFound: "Order not found in your scope",
  });
  if (state) return state;
  const d = detail.data;
  if (!d) return null;
  const o = d.order;
  return (
    <section className="mx-auto max-w-5xl space-y-6">
      <p className="text-sm">
        <Link to="/management/orders" className="underline">
          Orders &amp; Exceptions
        </Link>
      </p>
      <PageHeader title={`Order ${o.id.slice(0, 8)}`} updatedAt={detail.dataUpdatedAt}>
        <p className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="info" label={o.status_label} />
          {o.is_test_fixture ? <TestBadge label="Test order" /> : null}
          {o.delivery_exception_open ? <StatusBadge tone="danger" label="Exception open" /> : null}
        </p>
      </PageHeader>

      <dl className="grid gap-3 rounded-panel border border-border bg-surface p-4 text-sm sm:grid-cols-3">
        <Fact term="Placed" value={formatDateTime(o.placed_at)} />
        <Fact term="Kitchen" value={o.kitchen_name} />
        <Fact term="Payable" value={formatPaise(o.payable_paise)} />
        <Fact
          term="Payment"
          value={`${o.payment_method ?? "—"} · ${o.payment_status ? humanize(o.payment_status) : "—"}`}
        />
        <Fact term="Agent" value={o.agent_name ?? "—"} />
        <Fact term="Assignment" value={o.assignment_status ? humanize(o.assignment_status) : "—"} />
      </dl>

      {o.fulfilment_status === "DELIVERY_FAILED" ? (
        <p
          className="rounded-panel border border-dashed border-border p-3 text-sm"
          data-testid="refund-pending"
        >
          Refund decision pending: exceptional refunds are disabled because no threshold is configured
          (DDR-44).
        </p>
      ) : null}

      <Actions order={o} />

      <section aria-labelledby="items">
        <h2 id="items" className="text-lg font-semibold">
          Items
        </h2>
        <ul className="mt-2 space-y-1 text-sm">
          {d.items.map((i, n) => (
            <li key={`${i.name}-${n}`}>
              {i.quantity} × {i.name}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="timeline" className="space-y-2">
        <h2 id="timeline" className="text-lg font-semibold">
          Timeline
        </h2>
        <TableBox label="Timeline">
          <thead className="bg-muted">
            <tr>
              <Th>When</Th>
              <Th>What</Th>
              <Th>Change</Th>
              <Th>By</Th>
              <Th>Reason</Th>
            </tr>
          </thead>
          <tbody>
            {d.timeline.map((t, n) => (
              <tr key={`${t.changed_at}-${n}`} className="border-t border-border">
                <Td>{formatDateTime(t.changed_at)}</Td>
                <Td>{humanize(t.machine)}</Td>
                <Td>
                  {t.from_status ? `${humanize(t.from_status)} → ` : ""}
                  {humanize(t.to_status)}
                </Td>
                <Td>
                  {t.actor_name ?? "System"}
                  <span className="block text-xs text-text-muted">{humanize(t.actor_role)}</span>
                </Td>
                <Td>{t.reason ?? "—"}</Td>
              </tr>
            ))}
          </tbody>
        </TableBox>
      </section>
    </section>
  );
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <dt className="text-text-muted">{term}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function Actions({ order }: { order: OrderRow }) {
  const canAssign = useCan("management.agents.assign");
  const canReject = useCan("kitchen.orders.reject_accepted");
  const cannotFulfil = useCannotFulfil();
  const decide = useFailureDecision();
  const reissue = useReissueCode();
  const held = KITCHEN_HOLDS.includes(order.fulfilment_status);
  const failure = order.assignment_status === "FAILURE_REQUESTED";
  const onTheWay = order.fulfilment_status === "OUT_FOR_DELIVERY";

  const items = [
    canAssign && held && !failure ? <AssignAgent key="assign" order={order} /> : null,
    canAssign && failure ? (
      <ReasonAction
        key="approve"
        label="Approve failure"
        prompt="Why are you approving the delivery failure?"
        confirmLabel="Approve failure"
        onConfirm={(reason) => decide.mutateAsync({ orderId: order.id, approve: true, reason })}
      />
    ) : null,
    canAssign && failure ? (
      <ReasonAction
        key="return"
        label="Return to agent"
        prompt="Why should the agent continue the delivery?"
        confirmLabel="Return to agent"
        onConfirm={(reason) => decide.mutateAsync({ orderId: order.id, approve: false, reason })}
      />
    ) : null,
    canAssign && onTheWay && order.delivery_exception_open ? (
      <ReasonAction
        key="code"
        label="Issue new delivery code"
        prompt="Why is a new delivery code needed?"
        confirmLabel="Issue new code"
        onConfirm={(reason) => reissue.mutateAsync({ orderId: order.id, reason })}
      />
    ) : null,
    canReject && held ? (
      <ReasonAction
        key="reject"
        label="Cannot fulfil"
        prompt="Why can the kitchen not fulfil this order?"
        confirmLabel="Reject order"
        onConfirm={(reason) => cannotFulfil.mutateAsync({ orderId: order.id, reason })}
      />
    ) : null,
  ].filter(Boolean);

  if (items.length === 0) return null;
  return (
    <section aria-labelledby="actions" className="space-y-2">
      <h2 id="actions" className="text-lg font-semibold">
        Actions
      </h2>
      <div className="flex flex-col gap-3">{items}</div>
    </section>
  );
}

function AssignAgent({ order }: { order: OrderRow }) {
  const agents = useAgents();
  const assign = useAssignAgent();
  const [agentId, setAgentId] = useState("");
  const id = useId();
  const online = (agents.data ?? []).filter((a) => a.availability === "ONLINE" && !a.live_status);
  if (online.length === 0) {
    return <p className="text-sm">No online agent is free to assign right now.</p>;
  }
  const chosen = agentId || online[0]?.id || "";
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium">
        {order.agent_name ? "Reassign to" : "Assign to"}
      </label>
      <select id={id} value={chosen} onChange={(e) => setAgentId(e.target.value)} className={INPUT}>
        {online.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>
      <div>
        <ReasonAction
          label={order.agent_name ? "Reassign agent" : "Assign agent"}
          prompt="Why are you assigning this agent?"
          confirmLabel="Assign agent"
          onConfirm={(reason) => assign.mutateAsync({ orderId: order.id, agentId: chosen, reason })}
        />
      </div>
    </div>
  );
}
