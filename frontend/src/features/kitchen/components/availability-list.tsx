import type { ReactNode } from "react";

import type { AvailabilityRequest } from "../api";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge, type StatusTone } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime } from "@/shared/utils/format";

const STATUS: Record<AvailabilityRequest["status"], [StatusTone, string]> = {
  PENDING: ["warning", "Waiting for decision"],
  APPROVED: ["success", "Approved"],
  REJECTED: ["danger", "Rejected"],
};
const KIND: Record<AvailabilityRequest["kind"], string> = {
  MAKE_UNAVAILABLE: "Make unavailable",
  MAKE_AVAILABLE: "Make available again",
};

/** Requests with their reason, requester and decision (audited; DDR-111 (7)). */
export function AvailabilityList({
  rows,
  actions,
}: {
  rows: AvailabilityRequest[];
  actions?: (row: AvailabilityRequest) => ReactNode;
}) {
  if (rows.length === 0) return <EmptyState title="No requests" />;
  return (
    <ul className="space-y-2" aria-label="Dish availability requests">
      {rows.map((r) => {
        const [tone, label] = STATUS[r.status];
        return (
          <li
            key={r.id}
            className="rounded-panel border border-border bg-surface p-3 text-sm"
            data-testid="availability-request"
          >
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{r.dish_name}</span>
              {r.is_test_fixture ? <TestBadge /> : null}
              <span>· {KIND[r.kind]}</span>
              <StatusBadge tone={tone} label={label} />
            </p>
            <p className="mt-1">Reason: {r.reason}</p>
            <p className="text-text-muted">
              Requested by {r.requested_by_name} on {formatDateTime(r.requested_at)}
              {r.decided_by_name
                ? ` · decided by ${r.decided_by_name} on ${formatDateTime(r.decided_at)}`
                : ""}
            </p>
            {r.decision_reason ? <p>Decision note: {r.decision_reason}</p> : null}
            {actions ? actions(r) : null}
          </li>
        );
      })}
    </ul>
  );
}
