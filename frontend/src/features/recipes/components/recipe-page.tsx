import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  ACTIONS,
  KM_SIGNOFFS,
  SIGNOFF_LABELS,
  SIGNOFF_STATUSES,
  useSignoff,
  useTransition,
  useVersion,
  type Action,
  type RecipeDetail,
  type SignoffType,
} from "../api";
import { actionError } from "@/shared/api/errors";
import { useCan } from "@/shared/auth/require-permission";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { StatusBadge } from "@/shared/ui/status-badge";
import { recipeStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime } from "@/shared/utils/format";

// Recipe detail: fields, ingredients, lineage, sign-offs and review items; KM workflow actions.
export function RecipePage() {
  const { versionId = "" } = useParams();
  const version = useVersion(versionId);
  const state = queryState(version, { loading: "Loading recipe…", notFound: "Recipe not found" });
  if (state) return state;
  if (!version.data) return null;
  const v = version.data;

  return (
    <section className="mx-auto max-w-5xl">
      <p className="text-sm">
        <Link to="/kitchen/recipes" className="underline">
          Recipes
        </Link>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">{v.name}</h1>
        <StatusBadge tone={recipeStatus(v.status)[0]} label={recipeStatus(v.status)[1]} />
        {v.is_test_fixture ? <TestBadge /> : null}
      </div>
      <p className="mt-1 text-sm text-text-muted">
        {v.source_menu_id ? `SOP card ${v.source_menu_id}` : "TEST recipe"} · version {v.version}
        {v.candidate_category ? ` · candidate category "${v.candidate_category}" (unconfirmed)` : ""}
      </p>
      {v.quarantine_reason ? (
        <p className="mt-3 rounded-control border border-status-warning p-3 text-sm">{v.quarantine_reason}</p>
      ) : null}
      <Workflow v={v} />
      <Signoffs v={v} />
      <Fields v={v} />
      <Ingredients v={v} />
      <ReviewItems v={v} />
      <Lineage v={v} />
    </section>
  );
}

function Workflow({ v }: { v: RecipeDetail }) {
  const canWorkflow = useCan("kitchen.recipes.workflow");
  const transition = useTransition(v.id);
  const [open, setOpen] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  if (!canWorkflow) return null;
  const available = ACTIONS.filter((a) => a.from === v.status);
  // Keep the confirmation visible after the last step (e.g. Activate leaves no further action).
  if (available.length === 0 && !message) return null;

  const blocked = (action: Action): string | null => {
    if (action === "submit" && v.open_review_items > 0)
      return `${v.open_review_items} open review item(s) must be acknowledged first.`;
    if (action === "activate" && !v.is_test_fixture)
      return "No SOP recipe is activated in this POC (DDR-50).";
    if (action === "activate" && v.missing_signoffs.length > 0)
      return `Missing sign-offs: ${v.missing_signoffs.map((s) => SIGNOFF_LABELS[s]).join(", ")}.`;
    return null;
  };

  return (
    <section aria-labelledby="workflow" className="mt-4 rounded-panel border border-border bg-surface p-4">
      <h2 id="workflow" className="text-lg font-semibold">
        Workflow
      </h2>
      <div className="mt-2 flex flex-wrap gap-2">
        {available.map((a) => (
          <Button
            key={a.action}
            variant={a.action === "activate" ? "primary" : "secondary"}
            onClick={() => {
              setMessage(null);
              setOpen(a.action);
            }}
            aria-expanded={open === a.action}
          >
            {a.label}
          </Button>
        ))}
      </div>
      {available.map((a) =>
        a.action === open ? (
          <div key={a.action}>
            {blocked(a.action) ? <p className="mt-2 text-sm text-text-muted">{blocked(a.action)}</p> : null}
            <ReasonForm
              label={`Reason for "${a.label}"`}
              confirmLabel={a.confirm}
              hint="Recorded in the recipe's audit history."
              onCancel={() => setOpen(null)}
              onConfirm={async (reason) => {
                try {
                  await transition.mutateAsync({ action: a.action, reason });
                } catch (e) {
                  throw new Error(actionError(e), { cause: e });
                }
                setOpen(null);
                setMessage(`${a.label}: done.`);
              }}
            />
          </div>
        ) : null,
      )}
      {message ? (
        <p role="status" className="mt-2 text-sm">
          {message}
        </p>
      ) : null}
      {available.length === 0 ? (
        <p className="mt-1 text-sm text-text-muted">No further workflow step applies in this status.</p>
      ) : null}
    </section>
  );
}

function Signoffs({ v }: { v: RecipeDetail }) {
  const canSign = useCan("kitchen.recipes.signoff");
  const signoff = useSignoff(v.id);
  const [open, setOpen] = useState<SignoffType | null>(null);
  const signable = canSign && v.is_test_fixture && SIGNOFF_STATUSES.includes(v.status);
  const missingKm = KM_SIGNOFFS.filter((s) => v.missing_signoffs.includes(s));

  return (
    <section aria-labelledby="signoffs" className="mt-6">
      <h2 id="signoffs" className="text-lg font-semibold">
        Release sign-offs
      </h2>
      <p className="mt-1 text-sm text-text-muted">
        All five are required before activation. Recording them does not activate the recipe (DDR-10).
      </p>
      <ul className="mt-2 divide-y divide-border rounded-panel border border-border bg-surface text-sm">
        {v.signoffs.map((s) => (
          <li key={s.signoff_type} className="flex flex-wrap justify-between gap-2 p-3">
            <span className="font-medium">{SIGNOFF_LABELS[s.signoff_type]}</span>
            <span className="text-text-muted">
              Recorded {formatDateTime(s.signed_at)}
              {s.note ? ` · ${s.note}` : ""}
            </span>
          </li>
        ))}
        {v.missing_signoffs.map((s) => (
          <li key={s} className="p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <span className="font-medium">{SIGNOFF_LABELS[s]}</span>{" "}
                <span className="text-text-muted">· not recorded</span>
              </span>
              {signable && missingKm.includes(s) ? (
                <Button variant="secondary" onClick={() => setOpen(s)} aria-expanded={open === s}>
                  Record sign-off
                </Button>
              ) : null}
            </div>
            {open === s ? (
              <ReasonForm
                label={`Note for the ${SIGNOFF_LABELS[s]} sign-off`}
                confirmLabel="Confirm sign-off"
                onCancel={() => setOpen(null)}
                onConfirm={async (note) => {
                  try {
                    await signoff.mutateAsync({ type: s, note });
                  } catch (e) {
                    throw new Error(actionError(e), { cause: e });
                  }
                  setOpen(null);
                }}
              />
            ) : null}
          </li>
        ))}
      </ul>
      {v.missing_signoffs.includes("PRODUCT_OWNER") && v.is_test_fixture ? (
        <p className="mt-1 text-xs text-text-muted">
          The product-owner sign-off is recorded by a Central Administrator.
        </p>
      ) : null}
    </section>
  );
}

const FIELD_LABELS: [keyof RecipeDetail, string][] = [
  ["prep_type", "Preparation"],
  ["portion", "Portion"],
  ["method", "Method"],
  ["quality", "Quality"],
  ["inventory_rule", "Inventory"],
  ["validation_text", "Validation"],
];

function Fields({ v }: { v: RecipeDetail }) {
  return (
    <section aria-labelledby="fields" className="mt-6">
      <h2 id="fields" className="text-lg font-semibold">
        Recipe card
      </h2>
      <dl className="mt-2 space-y-2 rounded-panel border border-border bg-surface p-3 text-sm">
        {FIELD_LABELS.map(([key, label]) => (
          <div key={key}>
            <dt className="font-medium">{label}</dt>
            <dd className="text-text-muted">{(v[key] as string | null) ?? "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Ingredients({ v }: { v: RecipeDetail }) {
  return (
    <section aria-labelledby="ingredients" className="mt-6">
      <h2 id="ingredients" className="text-lg font-semibold">
        Ingredients per serving
      </h2>
      <div className="mt-2 overflow-x-auto rounded-panel border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted">
            <tr>
              <th scope="col" className="p-2">
                #
              </th>
              <th scope="col" className="p-2">
                Ingredient
              </th>
              <th scope="col" className="p-2">
                Quantity
              </th>
              <th scope="col" className="p-2">
                Source line
              </th>
            </tr>
          </thead>
          <tbody>
            {v.ingredients.map((i) => (
              <tr key={i.line_no} className="border-t border-border">
                <td className="p-2">{i.line_no}</td>
                <td className="p-2">{i.name}</td>
                <td className="p-2">
                  {i.quantity} {i.unit}
                </td>
                <td className="p-2">{i.source_line ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReviewItems({ v }: { v: RecipeDetail }) {
  if (v.review_items.length === 0) return null;
  return (
    <section aria-labelledby="review" className="mt-6">
      <h2 id="review" className="text-lg font-semibold">
        Review items
      </h2>
      <ul className="mt-2 divide-y divide-border rounded-panel border border-border bg-surface text-sm">
        {v.review_items.map((r) => (
          <li key={r.id} className="p-3">
            <span className="font-medium">{r.subject}</span> ·{" "}
            <span className="font-mono text-xs">{r.reason_code}</span> ·{" "}
            {r.status === "OPEN" ? "Open" : `Acknowledged: ${r.note ?? ""}`}
            <p className="text-text-muted">
              {r.detail} ({r.source_ref})
            </p>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-sm">
        <Link to="/kitchen/review-queue" className="underline">
          Open the review queue
        </Link>
      </p>
    </section>
  );
}

function Lineage({ v }: { v: RecipeDetail }) {
  const l = v.lineage;
  if (!l.source_sha256) return null;
  return (
    <section aria-labelledby="lineage" className="mt-6">
      <h2 id="lineage" className="text-lg font-semibold">
        Source lineage
      </h2>
      <dl className="mt-2 grid gap-1 rounded-panel border border-border bg-surface p-3 text-sm">
        <div>
          <dt className="inline font-medium">File: </dt>
          <dd className="inline break-all">{l.source_path}</dd>
        </div>
        <div>
          <dt className="inline font-medium">SHA-256: </dt>
          <dd className="inline break-all font-mono text-xs">{l.source_sha256}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Lines: </dt>
          <dd className="inline">
            {l.source_line_start}–{l.source_line_end}
            {l.source_page_ref ? ` (page ${l.source_page_ref})` : ""}
          </dd>
        </div>
      </dl>
    </section>
  );
}
