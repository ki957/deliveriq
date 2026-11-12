import { useState } from "react";
import { Link } from "react-router";

import { useAcknowledge, useReviewItems, type ReviewItem } from "../api";
import { actionError } from "@/shared/api/errors";
import { useCan } from "@/shared/auth/require-permission";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { humanize } from "@/shared/utils/format";

type Filter = "OPEN" | "ACKNOWLEDGED" | "ALL";

// Review queue (DDR-103): Kitchen Staff view; the Kitchen Manager acknowledges with a note.
// Acknowledging never edits recipe data; the open questions stay owner decisions (DDR-33–36).
export function ReviewQueuePage() {
  const [filter, setFilter] = useState<Filter>("OPEN");
  const items = useReviewItems(filter);
  const state = queryState(items, { loading: "Loading review items…" });

  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Review queue</h1>
      <p className="mt-1 text-sm text-text-muted">
        Questions found by the SOP import, with the source that raised them. Acknowledging records that the
        item was seen; it does not change the recipe.
      </p>
      <div className="mt-4">
        <label htmlFor="review-filter" className="block text-sm font-medium">
          Show
        </label>
        <select
          id="review-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value as Filter)}
          className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
        >
          <option value="OPEN">Open</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
          <option value="ALL">All</option>
        </select>
      </div>
      {state ??
        (items.data && items.data.length > 0 ? (
          <ul className="mt-4 divide-y divide-border rounded-panel border border-border bg-surface">
            {items.data.map((item) => (
              <ReviewRow key={item.id} item={item} />
            ))}
          </ul>
        ) : (
          <EmptyState title={filter === "OPEN" ? "No open review items" : "No review items"} />
        ))}
    </section>
  );
}

function ReviewRow({ item }: { item: ReviewItem }) {
  const canAck = useCan("kitchen.review.acknowledge");
  const acknowledge = useAcknowledge();
  const [open, setOpen] = useState(false);
  return (
    <li className="p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">
            {item.subject} ·{" "}
            <Link to={`/kitchen/recipes/${item.recipe_version_id}`} className="underline">
              {item.source_card_id ? `${item.source_card_id} ${item.recipe_name}` : item.recipe_name}
            </Link>
          </p>
          <p className="text-text-muted">
            {humanize(item.reason_code)}: {item.detail} ({item.source_ref}
            {item.source_line ? `, line ${item.source_line}` : ""})
          </p>
          {item.status === "ACKNOWLEDGED" ? <p className="text-text-muted">Note: {item.note}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            tone={item.status === "OPEN" ? "warning" : "success"}
            label={item.status === "OPEN" ? "Open" : "Acknowledged"}
          />
          {canAck && item.status === "OPEN" ? (
            <Button variant="secondary" onClick={() => setOpen(true)} aria-expanded={open}>
              Acknowledge
            </Button>
          ) : null}
        </div>
      </div>
      {open ? (
        <ReasonForm
          label={`Note for "${item.subject}"`}
          confirmLabel="Confirm acknowledgement"
          maxLength={1000}
          onCancel={() => setOpen(false)}
          onConfirm={async (note) => {
            try {
              await acknowledge.mutateAsync({ id: item.id, note });
            } catch (e) {
              throw new Error(actionError(e), { cause: e });
            }
            setOpen(false);
          }}
        />
      ) : null}
    </li>
  );
}
