import { useState } from "react";

import {
  useApproveKitchenGoldenSet,
  useDecideKitchenKnowledge,
  useKitchenGoldenSet,
  useKitchenKnowledgeVersions,
} from "../knowledge-api";
import { useCan } from "@/shared/auth/require-permission";
import { EmptyState } from "@/shared/ui/states";
import { queryState } from "@/shared/ui/query-state";

export function KitchenKnowledgePage() {
  const canApprove = useCan("kitchen.knowledge.approve");
  const versions = useKitchenKnowledgeVersions(canApprove);
  const goldenSet = useKitchenGoldenSet(canApprove);
  const decide = useDecideKitchenKnowledge();
  const approveGoldenSet = useApproveKitchenGoldenSet();
  const [reason, setReason] = useState("");
  const [goldenReason, setGoldenReason] = useState("");
  const state = queryState(versions, { loading: "Loading Kitchen knowledge…" });
  if (state) return state;

  return (
    <main className="mx-auto max-w-5xl space-y-6" aria-labelledby="kitchen-knowledge-title">
      <header>
        <h1 id="kitchen-knowledge-title" className="text-2xl font-semibold">
          Kitchen Knowledge approval
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Draft Kitchen guidance stays unavailable to the Copilot until a Kitchen Manager approves it.
          Decisions are audited and scoped to your kitchen.
        </p>
      </header>

      <section
        className="rounded-panel border border-border bg-surface p-4"
        aria-labelledby="knowledge-versions-title"
      >
        <h2 id="knowledge-versions-title" className="font-semibold">
          Document versions
        </h2>
        {versions.data?.length ? (
          <ul className="mt-3 divide-y divide-border rounded-control border border-border">
            {versions.data.map((version) => (
              <li key={`${version.id}-${version.kitchen_id}`} className="space-y-3 p-4">
                <div>
                  <p className="font-medium">{version.display_name}</p>
                  <p className="text-sm text-text-muted">
                    Version {version.doc_version} · {version.status} · SHA{" "}
                    {version.content_sha256.slice(0, 12)}…
                  </p>
                </div>
                {version.status === "DRAFT" ? (
                  <div className="space-y-2">
                    <label className="block text-sm" htmlFor={`knowledge-reason-${version.id}`}>
                      Decision reason
                    </label>
                    <textarea
                      id={`knowledge-reason-${version.id}`}
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      minLength={3}
                      maxLength={500}
                      rows={2}
                      className="w-full rounded-control border border-border bg-surface p-2"
                    />
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
                        disabled={reason.trim().length < 3 || decide.isPending}
                        onClick={() => decide.mutate({ versionId: version.id, approve: true, reason })}
                      >
                        Approve and publish
                      </button>
                      <button
                        className="min-h-11 rounded-control border border-border px-4 disabled:opacity-50"
                        disabled={reason.trim().length < 3 || decide.isPending}
                        onClick={() => decide.mutate({ versionId: version.id, approve: false, reason })}
                      >
                        Reject draft
                      </button>
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No Kitchen knowledge versions are staged" />
        )}
      </section>

      <section
        className="rounded-panel border border-border bg-surface p-4"
        aria-labelledby="golden-set-title"
      >
        <h2 id="golden-set-title" className="font-semibold">
          DDR-90 Kitchen golden set
        </h2>
        {goldenSet.data ? (
          <div className="mt-3 space-y-3 text-sm">
            <p>{goldenSet.data.name}</p>
            <p className="text-text-muted">
              {goldenSet.data.case_count} cases · {goldenSet.data.leak_count} leaks ·{" "}
              {goldenSet.data.approval_label}
            </p>
            {goldenSet.data.status === "DRAFT" ? (
              <>
                <label className="block" htmlFor="golden-set-reason">
                  Approval reason
                </label>
                <textarea
                  id="golden-set-reason"
                  value={goldenReason}
                  onChange={(event) => setGoldenReason(event.target.value)}
                  minLength={3}
                  maxLength={500}
                  rows={2}
                  className="w-full rounded-control border border-border bg-surface p-2"
                />
                <button
                  className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
                  disabled={
                    goldenReason.trim().length < 3 ||
                    goldenSet.data.case_count === 0 ||
                    goldenSet.data.leak_count !== 0 ||
                    approveGoldenSet.isPending
                  }
                  onClick={() => approveGoldenSet.mutate({ setId: goldenSet.data.id, reason: goldenReason })}
                >
                  Approve golden set
                </button>
                {goldenSet.data.case_count === 0 ? (
                  <p role="status">The draft set has no approved DDR-90 cases yet.</p>
                ) : null}
              </>
            ) : null}
          </div>
        ) : (
          <EmptyState title="No Kitchen golden set is registered" />
        )}
      </section>
    </main>
  );
}
