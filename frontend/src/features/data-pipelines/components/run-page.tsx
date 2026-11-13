import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  inputLabel,
  isActive,
  reportHref,
  useCancelRun,
  useRetryRun,
  useRunDetail,
  type RunDetail,
} from "../api";
import { actionError } from "@/shared/api/errors";
import { useCan } from "@/shared/auth/require-permission";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { runStatus, stageStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime, formatDuration, humanize } from "@/shared/utils/format";

// Run detail (DATA_PIPELINE §12): stage timeline, counts, durations, errors, quarantine, dq, report.
export function RunPage() {
  const { runId = "" } = useParams();
  const detail = useRunDetail(runId);
  const state = queryState(detail, { loading: "Loading run…", notFound: "Run not found" });
  if (state) return state;
  if (!detail.data) return null;
  const { run } = detail.data;
  const [tone, label] = runStatus(run.status);

  return (
    <section className="mx-auto max-w-5xl">
      <p className="text-sm">
        <Link to={`/management/data-pipelines/${run.pipeline}`} className="underline">
          Back to {run.pipeline}
        </Link>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">Run {run.id.slice(0, 8)}</h1>
        <span data-testid="run-status">
          <StatusBadge tone={tone} label={label} />
        </span>
        {run.is_test ? <TestBadge label="Test run" /> : null}
      </div>
      {isActive(run) ? (
        <p role="status" className="mt-1 text-sm text-text-muted">
          Refreshing every 2 seconds while the run is active.
        </p>
      ) : null}
      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Field term="Input" value={inputLabel(run.input_ref)} />
        <Field term="Trigger" value={run.trigger} />
        <Field term="Queued" value={formatDateTime(run.queued_at)} />
        <Field term="Started" value={formatDateTime(run.started_at)} />
        <Field term="Finished" value={formatDateTime(run.finished_at)} />
        <Field term="Duration" value={formatDuration(run.started_at, run.finished_at)} />
        {run.retry_of ? (
          <Field
            term="Retry of"
            value={
              <Link to={`/management/data-pipelines/runs/${run.retry_of}`} className="underline">
                {run.retry_of.slice(0, 8)}
              </Link>
            }
          />
        ) : null}
        {run.failure_class ? <Field term="Failure class" value={humanize(run.failure_class)} /> : null}
      </dl>
      {run.error_summary ? (
        <p className="mt-3 rounded-control border border-status-danger p-3 text-sm">{run.error_summary}</p>
      ) : null}
      <RunActions detail={detail.data} />
      <Counts counts={run.counts} />
      <Stages detail={detail.data} />
      <Errors detail={detail.data} />
      <Quality detail={detail.data} />
    </section>
  );
}

function Field({ term, value }: { term: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="font-medium">{term}:</dt>
      <dd>{value}</dd>
    </div>
  );
}

function RunActions({ detail }: { detail: RunDetail }) {
  const { run } = detail;
  const canOperate = useCan("pipelines.operate");
  const cancel = useCancelRun(run.id);
  const retry = useRetryRun(run.id);
  const navigate = useNavigate();
  const [message, setMessage] = useState<string | null>(null);

  async function doCancel() {
    setMessage(null);
    try {
      const result = await cancel.mutateAsync();
      setMessage(
        result.outcome === "cancelled"
          ? "Run cancelled."
          : "Cancel requested: the run stops at the next stage.",
      );
    } catch (e) {
      setMessage(actionError(e));
    }
  }

  async function doRetry() {
    setMessage(null);
    try {
      const created = await retry.mutateAsync();
      navigate(`/management/data-pipelines/runs/${created.id}`);
    } catch (e) {
      setMessage(actionError(e));
    }
  }

  const canCancel = canOperate && isActive(run) && !run.cancel_requested;
  const canRetry = canOperate && (run.status === "failed" || run.status === "cancelled");
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      {run.has_report ? (
        <Button variant="secondary" asChild>
          <a href={reportHref(run.id)} download>
            Download report
          </a>
        </Button>
      ) : null}
      {canCancel ? (
        <Button variant="secondary" onClick={doCancel} disabled={cancel.isPending}>
          Cancel run
        </Button>
      ) : null}
      {canRetry ? (
        <Button onClick={doRetry} disabled={retry.isPending}>
          Retry run
        </Button>
      ) : null}
      {run.cancel_requested && isActive(run) ? (
        <span className="text-sm text-text-muted">Cancel requested</span>
      ) : null}
      {message ? (
        <p role="status" className="w-full text-sm">
          {message}
        </p>
      ) : null}
    </div>
  );
}

function Counts({ counts }: { counts: Record<string, unknown> }) {
  const scalars = Object.entries(counts).filter(([, v]) => typeof v === "number");
  const added = counts.added && typeof counts.added === "object" ? Object.entries(counts.added) : [];
  if (scalars.length === 0 && added.length === 0) return null;
  return (
    <section aria-labelledby="counts" className="mt-6">
      <h2 id="counts" className="text-lg font-semibold">
        Counts
      </h2>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {scalars.map(([k, v]) => (
          <div key={k} className="rounded-panel border border-border bg-surface p-2">
            <dt className="text-text-muted">{humanize(k)}</dt>
            <dd className="text-lg font-semibold" data-testid={`count-${k}`}>
              {String(v)}
            </dd>
          </div>
        ))}
        {added.map(([k, v]) => (
          <div key={`added-${k}`} className="rounded-panel border border-border bg-surface p-2">
            <dt className="text-text-muted">Added: {humanize(k)}</dt>
            <dd className="text-lg font-semibold">{String(v)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Stages({ detail }: { detail: RunDetail }) {
  return (
    <section aria-labelledby="stages" className="mt-6">
      <h2 id="stages" className="text-lg font-semibold">
        Stages
      </h2>
      {detail.stages.length === 0 ? (
        <p className="mt-2 text-sm text-text-muted">No stage has started.</p>
      ) : (
        <ol className="mt-2 divide-y divide-border rounded-panel border border-border bg-surface">
          {detail.stages.map((s) => (
            <li key={s.seq} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
              <span className="font-medium">
                {s.seq}. {s.stage}
              </span>
              <span className="flex flex-wrap items-center gap-3 text-text-muted">
                {s.rows_in !== null ? <span>in {s.rows_in}</span> : null}
                {s.rows_out !== null ? <span>out {s.rows_out}</span> : null}
                {s.rows_rejected !== null ? <span>rejected {s.rows_rejected}</span> : null}
                <span>{formatDuration(s.started_at, s.finished_at)}</span>
                <StatusBadge tone={stageStatus(s.status)[0]} label={stageStatus(s.status)[1]} />
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Errors({ detail }: { detail: RunDetail }) {
  return (
    <section aria-labelledby="errors" className="mt-6">
      <h2 id="errors" className="text-lg font-semibold">
        Quarantined records and errors
      </h2>
      {detail.errors_total === 0 ? (
        <p className="mt-2 text-sm text-text-muted">None recorded.</p>
      ) : (
        <>
          <p className="mt-1 text-sm text-text-muted">
            Showing {detail.errors.length} of {detail.errors_total}.
          </p>
          <div className="mt-2 overflow-x-auto rounded-panel border border-border bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted">
                <tr>
                  <th scope="col" className="p-2">
                    Record
                  </th>
                  <th scope="col" className="p-2">
                    Reason
                  </th>
                  <th scope="col" className="p-2">
                    Detail
                  </th>
                  <th scope="col" className="p-2">
                    Stage
                  </th>
                </tr>
              </thead>
              <tbody>
                {detail.errors.map((e, i) => (
                  <tr key={`${e.record_ref}-${i}`} className="border-t border-border">
                    <td className="p-2">{e.record_ref ?? "—"}</td>
                    <td className="p-2 font-mono text-xs">{e.reason_code}</td>
                    <td className="p-2">{e.message}</td>
                    <td className="p-2">{e.stage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function Quality({ detail }: { detail: RunDetail }) {
  if (detail.dq_results.length === 0) return null;
  return (
    <section aria-labelledby="quality" className="mt-6">
      <h2 id="quality" className="text-lg font-semibold">
        Quality checks
      </h2>
      <ul className="mt-2 divide-y divide-border rounded-panel border border-border bg-surface">
        {detail.dq_results.map((d) => (
          <li key={d.check_name} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
            <span>
              <span className="font-medium">{humanize(d.check_name)}</span>{" "}
              <span className="text-text-muted">({d.severity})</span>
            </span>
            <span className="flex items-center gap-2">
              {d.failures ? <span className="text-text-muted">{d.failures} failing</span> : null}
              <StatusBadge
                tone={d.status === "pass" ? "success" : d.severity === "warning" ? "warning" : "danger"}
                label={d.status === "pass" ? "Pass" : humanize(d.status)}
              />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
