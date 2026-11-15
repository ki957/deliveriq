import { useEffect, useRef, useState } from "react";

import { useConfirmAction, useProposeAction, type ActionProposal, type ActionResult } from "../api";

function Fields({ values }: { values: Record<string, unknown> }) {
  return (
    <dl className="grid gap-1 text-sm">
      {Object.entries(values).map(([name, value]) => (
        <div key={name} className="grid grid-cols-2 gap-2">
          <dt className="font-medium">{name.replaceAll("_", " ")}</dt>
          <dd className="break-all">{String(value ?? "None")}</dd>
        </div>
      ))}
    </dl>
  );
}

export function OperationalActionsPage() {
  const propose = useProposeAction();
  const confirm = useConfirmAction();
  const [request, setRequest] = useState("");
  const [proposal, setProposal] = useState<ActionProposal | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [key, setKey] = useState("");
  const change = proposal?.exact_change;
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (proposal?.status === "proposed" && !dialog.open) dialog.showModal();
    if (proposal?.status !== "proposed" && dialog.open) dialog.close();
  }, [proposal]);

  return (
    <main className="mx-auto max-w-3xl space-y-6" aria-labelledby="actions-title">
      <header>
        <h1 id="actions-title" className="text-2xl font-semibold">
          Operational Actions
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Central Admin only. The assistant proposes a change; you review and confirm it before anything is
          written. Proposals use a simulated model in this local demo.
        </p>
      </header>

      <section className="rounded-panel border border-border bg-surface p-4">
        <h2 className="font-semibold">Request an action</h2>
        <p className="mt-2 text-sm text-text-muted">
          Include exact IDs, values and a reason. Supported requests: Set kitchen … to NORMAL/BUSY/PAUSED with
          normal capacity … and busy capacity …. Reason: …; Assign order … to agent …. Reason: …; Approve or
          Reject dish availability request …. Reason: …; Publish TEST menu item …. Reason: … .
        </p>
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            setProposal(null);
            setResult(null);
            if (!request.trim()) return;
            propose.mutate(request, {
              onSuccess: (next) => {
                setProposal(next);
                setKey(crypto.randomUUID());
              },
            });
          }}
        >
          <label htmlFor="action-request" className="block font-medium">
            Action request
          </label>
          <textarea
            id="action-request"
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            rows={4}
            maxLength={2000}
            className="w-full rounded-control border border-border bg-surface p-3"
          />
          <button
            className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
            disabled={propose.isPending || !request.trim()}
          >
            {propose.isPending ? "Preparing…" : "Preview change"}
          </button>
        </form>
        {propose.isError ? (
          <p role="alert" className="mt-3">
            The proposal could not be prepared.
          </p>
        ) : null}
        {proposal && proposal.status !== "proposed" ? (
          <p role="status" className="mt-3">
            {proposal.message}
          </p>
        ) : null}
      </section>

      {proposal?.status === "proposed" && change ? (
        <dialog
          ref={dialogRef}
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          onCancel={() => setProposal(null)}
          className="w-[min(95vw,42rem)] rounded-panel border border-border bg-surface p-4 text-text backdrop:bg-black/50"
        >
          <h2 id="confirm-title" className="font-semibold">
            Review exact change
          </h2>
          <p className="mt-1 text-sm">{proposal.message}</p>
          <p className="mt-2 break-all text-sm">Target: {String(change.target)}</p>
          {change.dish ? <p className="text-sm">Dish: {String(change.dish)}</p> : null}
          <p className="mt-2 text-sm">Reason: {String(change.reason)}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="mb-2 font-medium">Current</h3>
              <Fields values={(change.before ?? {}) as Record<string, unknown>} />
            </div>
            <div>
              <h3 className="mb-2 font-medium">After</h3>
              <Fields values={(change.after ?? {}) as Record<string, unknown>} />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
              disabled={confirm.isPending || !proposal.proposal_id}
              onClick={() => {
                if (!proposal.proposal_id) return;
                confirm.mutate(
                  { proposalId: proposal.proposal_id, idempotencyKey: key },
                  {
                    onSuccess: (done) => {
                      setResult(done);
                      setProposal(null);
                    },
                  },
                );
              }}
            >
              {confirm.isPending ? "Confirming…" : "Confirm exact change"}
            </button>
            <button
              className="min-h-11 rounded-control border border-border px-4"
              onClick={() => setProposal(null)}
            >
              Cancel
            </button>
          </div>
          {confirm.isError ? (
            <p role="alert" className="mt-3">
              Confirmation failed. If the target changed, request a fresh proposal. A retry uses the same
              confirmation key.
            </p>
          ) : null}
        </dialog>
      ) : null}

      {result ? (
        <p role="status" className="rounded-panel border border-border bg-surface p-4">
          Action confirmed and audited.
        </p>
      ) : null}
      <p className="text-sm text-text-muted">
        Promotions, review moderation, regional settings and exceptional refunds are unavailable until their
        rules are approved.
      </p>
    </main>
  );
}
