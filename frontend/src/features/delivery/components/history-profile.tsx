import { useState } from "react";

import { refusalText, useHistory, useRename } from "../api";
import { useMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime } from "@/shared/utils/format";

// #7 §9: own deliveries of the last 30 days; duration only where reliable (pickup → delivered).
export function DeliveryHistoryPage() {
  const history = useHistory();
  const state = queryState(history, { loading: "Loading history…" });
  const rows = history.data ?? [];
  return (
    <section className="mx-auto max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">History</h1>
      <p className="text-sm text-text-muted">Your deliveries of the last 30 days. No earnings are shown.</p>
      {state ??
        (rows.length === 0 ? (
          <EmptyState title="No deliveries yet" />
        ) : (
          <ul className="space-y-2" aria-label="Past deliveries">
            {rows.map((r) => (
              <li
                key={`${r.order_id}-${r.offered_at}`}
                className="rounded-panel border border-border bg-surface p-3 text-sm"
              >
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  Order {r.order_id.slice(0, 8)}
                  {r.is_test_fixture ? <TestBadge label="Test order" /> : null}
                  <StatusBadge
                    tone={r.fulfilment_status === "DELIVERED" ? "success" : "danger"}
                    label={r.fulfilment_status === "DELIVERED" ? "Delivered" : "Failed"}
                  />
                </p>
                <p>
                  {formatDateTime(r.delivered_at ?? r.offered_at)}
                  {r.duration_minutes !== null ? ` · ${r.duration_minutes} min from pickup` : ""}
                </p>
              </li>
            ))}
          </ul>
        ))}
    </section>
  );
}

// #7 §9, DDR-113 (15): the name is editable; the mobile changes only through recovery; no photo storage.
export function DeliveryProfilePage() {
  const me = useMe();
  const rename = useRename();
  const [name, setName] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const value = name ?? me.data?.display_name ?? "";
  return (
    <section className="mx-auto max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">Profile</h1>
      <form
        className="space-y-2 rounded-panel border border-border bg-surface p-4"
        noValidate
        onSubmit={async (e) => {
          e.preventDefault();
          setMessage(null);
          try {
            const saved = await rename.mutateAsync(value);
            setMessage(`Saved as ${saved.display_name}.`);
          } catch (err) {
            setMessage(refusalText(err));
          }
        }}
      >
        <label htmlFor="agent-name" className="block font-medium">
          Name
        </label>
        <input
          id="agent-name"
          value={value}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          className={`w-full ${INPUT}`}
        />
        <Button type="submit" disabled={rename.isPending || !value.trim()}>
          Save name
        </Button>
        {message ? <p role="status">{message}</p> : null}
      </form>
      <p className="text-sm text-text-muted">
        Profile photos are not available in this POC (no file storage). Your mobile number changes only
        through account recovery.
      </p>
    </section>
  );
}
