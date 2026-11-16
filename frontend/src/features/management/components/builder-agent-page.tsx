import { useState } from "react";

import { useBuilderTask, useConfirmBuilderTask, useProposeBuilderTask, type BuilderTask } from "../api";

export function BuilderAgentPage() {
  const [request, setRequest] = useState("");
  const [proposal, setProposal] = useState<BuilderTask | null>(null);
  const propose = useProposeBuilderTask();
  const confirm = useConfirmBuilderTask();
  const task = useBuilderTask(proposal?.task_id);
  const current = task.data ?? proposal;

  return (
    <main className="mx-auto max-w-4xl space-y-6" aria-labelledby="builder-title">
      <header>
        <h1 id="builder-title" className="text-2xl font-semibold">
          Builder Agent
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Central Admin only. The agent works in a disposable sandbox, runs unit tests, and shows you the
          exact diff. A pull request opens only after you confirm it; the repository owner merges on GitHub.
        </p>
      </header>

      <section
        className="rounded-panel border border-border bg-surface p-4"
        aria-label="Builder Agent request"
      >
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            setProposal(null);
            if (!request.trim()) return;
            propose.mutate(request, { onSuccess: setProposal });
          }}
        >
          <label htmlFor="builder-request" className="block font-medium">
            Change request
          </label>
          <textarea
            id="builder-request"
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            rows={5}
            maxLength={2000}
            className="w-full rounded-control border border-border bg-surface p-3"
          />
          <button
            className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
            type="submit"
            disabled={propose.isPending || !request.trim()}
          >
            {propose.isPending ? "Building and testing…" : "Prepare diff"}
          </button>
          {propose.isError && <p role="alert">The Builder Agent could not prepare a reviewable change.</p>}
        </form>
      </section>

      {current && (
        <section
          className="space-y-4 rounded-panel border border-border bg-surface p-4"
          aria-label="Review Builder Agent diff"
        >
          <h2 className="text-lg font-semibold">
            {current.status === "review" ? "Review proposed change" : "Builder Agent task"}
          </h2>
          {!["review", "opened", "failed"].includes(current.status) && (
            <p role="status">Waiting for the host Builder Agent runner…</p>
          )}
          {current.error_message && <p role="alert">{current.error_message}</p>}
          <p>{current.summary}</p>
          <p className="text-sm text-text-muted">
            Model: {current.logical_model ?? "strong"}. Unit tests:{" "}
            {current.test_result.passed === true
              ? current.test_result.runner === "mock"
                ? "passed (mock sandbox runner; code not executed)"
                : "passed"
              : "pending"}
          </p>
          <h3 className="font-medium">Changed files</h3>
          <ul className="list-inside list-disc">
            {current.changed_files.map((path) => (
              <li key={path} className="font-mono text-sm">
                {path}
              </li>
            ))}
          </ul>
          <pre
            tabIndex={0}
            className="max-h-[32rem] overflow-auto rounded-control border border-border bg-canvas p-3 text-xs"
          >
            <code>{current.diff}</code>
          </pre>
          {current.status === "opened" ? (
            <p role="status">
              Pull request opened on <span className="font-mono">{current.branch}</span>:{" "}
              <a className="underline" href={current.pull_request_url ?? "#"}>
                {current.pull_request_url}
              </a>
            </p>
          ) : current.status === "review" ? (
            <button
              className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
              type="button"
              disabled={confirm.isPending || current.test_result.passed !== true}
              onClick={() => confirm.mutate(current.task_id)}
            >
              {confirm.isPending ? "Confirming…" : "Confirm and open pull request"}
            </button>
          ) : null}
          {confirm.isError && (
            <p role="alert">
              The pull request could not be opened. The proposal remains available for review.
            </p>
          )}
        </section>
      )}
    </main>
  );
}
