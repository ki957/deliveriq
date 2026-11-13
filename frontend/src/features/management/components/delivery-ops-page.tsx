import { lazy, Suspense } from "react";
import { Link } from "react-router";

import { useAgents, useDeliveries, useForceOffline, type Agent, type Delivery } from "../api";
import { PageHeader, ReasonAction, TableBox, Td, Th } from "./common";
import { useCan } from "@/shared/auth/require-permission";
import { queryState } from "@/shared/ui/query-state";
import { LoadingState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, humanize } from "@/shared/utils/format";

const PositionsMap = lazy(() => import("./delivery-map"));

// DDR-114 (11): agents with availability and live work; the latest position per active delivery
// (Simulated labelled) in a table and a lazy map; force offline with a reason (DDR-113 (4)).
export function DeliveryOpsPage() {
  const deliveries = useDeliveries();
  const canAssign = useCan("management.agents.assign");
  const state = queryState(deliveries, { loading: "Loading deliveries…" });
  if (state) return state;
  const rows = deliveries.data ?? [];
  const located = rows.filter(
    (d): d is Delivery & { lat: number; lng: number } => d.lat !== null && d.lng !== null,
  );
  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <PageHeader title="Delivery Operations" updatedAt={deliveries.dataUpdatedAt} />

      {canAssign ? <AgentsSection /> : null}

      <section aria-labelledby="live" className="space-y-2">
        <h2 id="live" className="text-lg font-semibold">
          Live offers and deliveries
        </h2>
        {rows.length === 0 ? (
          <p className="text-sm">No live offers or deliveries in your scope.</p>
        ) : (
          <TableBox label="Live offers and deliveries">
            <thead className="bg-muted">
              <tr>
                <Th>Order</Th>
                <Th>Agent</Th>
                <Th>Assignment</Th>
                <Th>Latest position</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.assignment_id} className="border-t border-border">
                  <Td>
                    <Link to={`/management/orders/${d.order_id}`} className="underline">
                      {d.order_id.slice(0, 8)}
                    </Link>
                    <span className="mt-1 flex flex-wrap gap-1">
                      {d.is_test_fixture ? <TestBadge label="Test order" /> : null}
                      {d.delivery_exception_open ? (
                        <StatusBadge tone="danger" label="Exception open" />
                      ) : null}
                    </span>
                  </Td>
                  <Td>{d.agent_name}</Td>
                  <Td>
                    <StatusBadge
                      tone={d.assignment_status === "FAILURE_REQUESTED" ? "warning" : "info"}
                      label={humanize(d.assignment_status)}
                    />
                  </Td>
                  <Td>
                    {d.lat !== null && d.lng !== null ? (
                      <>
                        {d.lat.toFixed(5)}, {d.lng.toFixed(5)}{" "}
                        {d.simulated ? <TestBadge label="Simulated GPS" /> : null}
                        <span className="block text-xs text-text-muted">{formatDateTime(d.recorded_at)}</span>
                      </>
                    ) : (
                      "No position yet"
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableBox>
        )}
        {located.length > 0 ? (
          <Suspense fallback={<LoadingState label="Loading map…" />}>
            <PositionsMap deliveries={located} />
          </Suspense>
        ) : null}
      </section>
    </section>
  );
}

function AgentsSection() {
  const agents = useAgents();
  const state = queryState(agents, { loading: "Loading agents…" });
  return (
    <section aria-labelledby="agents" className="space-y-2">
      <h2 id="agents" className="text-lg font-semibold">
        Agents
      </h2>
      {state ??
        ((agents.data ?? []).length === 0 ? (
          <p className="text-sm">No delivery agents in your scope.</p>
        ) : (
          <ul className="space-y-2" aria-label="Agents">
            {(agents.data ?? []).map((a) => (
              <AgentRow key={a.id} agent={a} />
            ))}
          </ul>
        ))}
    </section>
  );
}

function AgentRow({ agent }: { agent: Agent }) {
  const forceOffline = useForceOffline();
  const online = agent.availability === "ONLINE";
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-panel border border-border bg-surface p-3">
      <span className="space-y-1">
        <span className="block font-medium">{agent.name}</span>
        <span className="flex flex-wrap items-center gap-2 text-sm">
          <StatusBadge tone={online ? "success" : "neutral"} label={humanize(agent.availability)} />
          {agent.live_status ? `Live: ${humanize(agent.live_status)}` : "No live work"}
        </span>
      </span>
      {online ? (
        <ReasonAction
          label="Force offline"
          prompt={`Why are you setting ${agent.name} offline?`}
          confirmLabel="Set offline"
          onConfirm={(reason) => forceOffline.mutateAsync({ agentId: agent.id, reason })}
        />
      ) : null}
    </li>
  );
}
