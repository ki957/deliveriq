import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { inputLabel, usePipelines, useRuns, useTriggerRun, type Pipeline } from "../api";
import { actionError } from "@/shared/api/errors";
import { useCan } from "@/shared/auth/require-permission";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { StatusBadge } from "@/shared/ui/status-badge";
import { runStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime } from "@/shared/utils/format";

// Pipeline detail (DATA_PIPELINE §12): Run for CA only; run history for CA and own-region RM.
export function PipelinePage() {
  const { pipeline: name = "" } = useParams();
  const pipelines = usePipelines();
  const state = queryState(pipelines, { loading: "Loading pipeline…" });
  if (state) return state;
  const pipeline = pipelines.data?.find((p) => p.name === name);
  if (!pipeline) return <EmptyState title="Pipeline not found" />;

  return (
    <section className="mx-auto max-w-5xl">
      <p className="text-sm">
        <Link to="/management/data-pipelines" className="underline">
          Data &amp; Pipelines
        </Link>
      </p>
      <h1 className="mt-1 text-2xl font-semibold">{pipeline.display_name}</h1>
      <RunControls pipeline={pipeline} />
      <RunHistory pipeline={pipeline.name} />
    </section>
  );
}

function RunControls({ pipeline }: { pipeline: Pipeline }) {
  const canOperate = useCan("pipelines.operate");
  const trigger = useTriggerRun();
  const navigate = useNavigate();
  const [input, setInput] = useState(pipeline.inputs[0] ?? "sop");
  const [error, setError] = useState<string | null>(null);
  if (!canOperate || !pipeline.implemented) return null;

  async function run() {
    setError(null);
    try {
      const created = await trigger.mutateAsync({ pipeline: pipeline.name, inputRef: input });
      navigate(`/management/data-pipelines/runs/${created.id}`);
    } catch (e) {
      setError(actionError(e));
    }
  }

  return (
    <div className="mt-4 rounded-panel border border-border bg-surface p-4" data-testid="run-controls">
      <h2 className="text-lg font-semibold">Run</h2>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="run-input" className="block text-sm font-medium">
            Input
          </label>
          <select
            id="run-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
          >
            {pipeline.inputs.map((ref) => (
              <option key={ref} value={ref}>
                {inputLabel(ref)}
              </option>
            ))}
          </select>
        </div>
        <Button onClick={run} disabled={trigger.isPending}>
          Run pipeline
        </Button>
      </div>
      {input.startsWith("fault:") ? (
        <p className="mt-2 text-sm text-text-muted">
          TEST fault files are written from scratch, run only in local/test, and never load into recipe
          tables.
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 rounded-control border border-status-danger p-2 text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}

// DDR-114 (13): run-history filters over the latest 50 runs the API returns (scope enforced there).
function RunHistory({ pipeline }: { pipeline: string }) {
  const runs = useRuns(pipeline);
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState<"all" | "test" | "real">("all");
  const state = queryState(runs, { loading: "Loading run history…" });
  const statuses = [...new Set((runs.data ?? []).map((r) => r.status))].sort();
  const shown = (runs.data ?? []).filter(
    (r) => (!status || r.status === status) && (kind === "all" || (kind === "test" ? r.is_test : !r.is_test)),
  );
  return (
    <section aria-labelledby="history" className="mt-6">
      <h2 id="history" className="text-lg font-semibold">
        Run history
      </h2>
      {runs.data && runs.data.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-end gap-3" data-testid="run-filters">
          <div>
            <label htmlFor="run-status" className="block text-sm font-medium">
              Status
            </label>
            <select
              id="run-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
            >
              <option value="">Any</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {runStatus(s)[1]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="run-kind" className="block text-sm font-medium">
              Runs
            </label>
            <select
              id="run-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as "all" | "test" | "real")}
              className="mt-1 min-h-11 rounded-control border border-border bg-surface px-3"
            >
              <option value="all">All</option>
              <option value="test">Test runs only</option>
              <option value="real">Real runs only</option>
            </select>
          </div>
          <p className="text-xs text-text-muted">
            Filters the latest {runs.data.length} runs · showing {shown.length}
          </p>
        </div>
      ) : null}
      {state ??
        (shown.length > 0 ? (
          <div className="mt-2 overflow-x-auto rounded-panel border border-border bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted">
                <tr>
                  <th scope="col" className="p-2">
                    Status
                  </th>
                  <th scope="col" className="p-2">
                    Input
                  </th>
                  <th scope="col" className="p-2">
                    Trigger
                  </th>
                  <th scope="col" className="p-2">
                    Queued
                  </th>
                  <th scope="col" className="p-2">
                    Finished
                  </th>
                  <th scope="col" className="p-2">
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((run) => (
                  <tr key={run.id} className="border-t border-border">
                    <td className="p-2">
                      <span className="flex flex-wrap gap-1">
                        <StatusBadge tone={runStatus(run.status)[0]} label={runStatus(run.status)[1]} />
                        {run.is_test ? <TestBadge label="Test run" /> : null}
                      </span>
                    </td>
                    <td className="p-2">{inputLabel(run.input_ref)}</td>
                    <td className="p-2">{run.trigger}</td>
                    <td className="p-2">{formatDateTime(run.queued_at)}</td>
                    <td className="p-2">{formatDateTime(run.finished_at)}</td>
                    <td className="p-2">
                      <Link to={`/management/data-pipelines/runs/${run.id}`} className="underline">
                        View run
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title={runs.data && runs.data.length > 0 ? "No runs match these filters" : "No runs yet"}
          />
        ))}
    </section>
  );
}
