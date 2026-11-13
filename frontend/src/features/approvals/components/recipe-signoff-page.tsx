import { useState } from "react";
import { Link, useParams } from "react-router";

import { useProductOwnerSignoff, useSignoffDetail, useSignoffQueue } from "../api";
import { actionError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { recipeStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";

// The product owner records the PRODUCT_OWNER sign-off through a CA account (DDR-54, DDR-106, DDR-108).
export function RecipeSignoffPage() {
  const queue = useSignoffQueue();
  const state = queryState(queue, { loading: "Loading recipes…" });
  if (state) return state;
  const rows = queue.data ?? [];

  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Recipe sign-off</h1>
      <p className="mt-1 text-sm text-text-muted">
        TEST recipes in validation. The Kitchen Manager records the other four sign-offs and activates.
      </p>
      {rows.length === 0 ? (
        <EmptyState title="No TEST recipes are awaiting sign-off" />
      ) : (
        <ul className="mt-4 divide-y divide-border rounded-panel border border-border bg-surface">
          {rows.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <Link to={`/management/recipe-signoff/${v.id}`} className="font-medium underline">
                  {v.name}
                </Link>
                <TestBadge />
              </span>
              <StatusBadge tone={recipeStatus(v.status)[0]} label={recipeStatus(v.status)[1]} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function RecipeSignoffDetailPage() {
  const { versionId = "" } = useParams();
  const detail = useSignoffDetail(versionId);
  const signoff = useProductOwnerSignoff(versionId);
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const state = queryState(detail, { loading: "Loading recipe…", notFound: "Recipe not found" });
  if (state) return state;
  if (!detail.data) return null;
  const v = detail.data;
  const recorded = v.signoffs.find((s) => s.signoff_type === "PRODUCT_OWNER");

  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-sm">
        <Link to="/management/recipe-signoff" className="underline">
          Recipe sign-off
        </Link>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">{v.name}</h1>
        <StatusBadge tone={recipeStatus(v.status)[0]} label={recipeStatus(v.status)[1]} />
        {v.is_test_fixture ? <TestBadge /> : null}
      </div>
      <p className="mt-3 text-sm">
        Recorded: {v.signoffs.length} of 5. Missing:{" "}
        {v.missing_signoffs.length ? v.missing_signoffs.join(", ") : "none"}.
      </p>
      {recorded ? (
        <p className="mt-3 text-sm" role="status">
          Product-owner sign-off recorded{recorded.note ? `: ${recorded.note}` : "."}
        </p>
      ) : open ? (
        <ReasonForm
          label="Note for the product-owner sign-off"
          confirmLabel="Confirm sign-off"
          onCancel={() => setOpen(false)}
          onConfirm={async (note) => {
            try {
              await signoff.mutateAsync(note);
            } catch (e) {
              throw new Error(actionError(e), { cause: e });
            }
            setOpen(false);
            setDone(true);
          }}
        />
      ) : (
        <Button className="mt-3" onClick={() => setOpen(true)} aria-expanded={open}>
          Record product-owner sign-off
        </Button>
      )}
      {done ? (
        <p role="status" className="mt-2 text-sm">
          Sign-off recorded.
        </p>
      ) : null}
    </section>
  );
}
