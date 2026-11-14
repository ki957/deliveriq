import { Link } from "react-router";

import { PLANNED_TASK, useBacklog, usePipelines, type Backlog, type Pipeline } from "../api";
import { useCan } from "@/shared/auth/require-permission";
import { EmptyState } from "@/shared/ui/states";
import { queryState } from "@/shared/ui/query-state";
import { StatusBadge } from "@/shared/ui/status-badge";
import { runStatus } from "@/shared/ui/status-tones";
import { TestBadge } from "@/shared/ui/test-badge";
import { formatDateTime } from "@/shared/utils/format";

const GROUPS: { key: string; title: string }[] = [
  { key: "DATA", title: "Data" },
  { key: "KNOWLEDGE", title: "Knowledge" },
  { key: "MAINTENANCE", title: "Maintenance" },
];

// DATA_PIPELINE_DESIGN §12 Overview: groups and last status, from persisted run records only.
export function PipelinesOverview() {
  const pipelines = usePipelines();
  const state = queryState(pipelines, { loading: "Loading pipelines…" });
  if (state) return state;
  const all = pipelines.data ?? [];
  if (all.length === 0) return <EmptyState title="No pipelines are registered" />;

  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Data &amp; Pipelines</h1>
      <p className="mt-1 text-sm text-text-muted">
        Run history and results come from the database. Pipelines not built yet are listed with the task that
        adds them.
      </p>
      {GROUPS.map(({ key, title }) => {
        const members = all.filter((p) => p.pipeline_group === key);
        if (members.length === 0) return null;
        return (
          <section key={key} aria-labelledby={`group-${key}`} className="mt-6">
            <h2 id={`group-${key}`} className="text-lg font-semibold">
              {title}
            </h2>
            <ul className="mt-2 divide-y divide-border rounded-panel border border-border bg-surface">
              {members.map((p) => (
                <PipelineRow key={p.name} pipeline={p} />
              ))}
            </ul>
            {key === "DATA" ? <BacklogPanel /> : null}
          </section>
        );
      })}
    </section>
  );
}

function PipelineRow({ pipeline }: { pipeline: Pipeline }) {
  const last = pipeline.last_run;
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <p className="font-medium">
          {pipeline.implemented ? (
            <Link to={`/management/data-pipelines/${pipeline.name}`} className="underline">
              {pipeline.display_name}
            </Link>
          ) : (
            pipeline.display_name
          )}
        </p>
        <p className="text-xs text-text-muted">
          {pipeline.is_heavy ? "Heavy job (one at a time)" : "Light job"}
          {last ? ` · last queued ${formatDateTime(last.queued_at)}` : ""}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {!pipeline.implemented ? (
          <span className="text-sm text-text-muted">
            Not built yet{PLANNED_TASK[pipeline.name] ? ` (Task ${PLANNED_TASK[pipeline.name]})` : ""}
          </span>
        ) : last ? (
          <>
            {last.is_test ? <TestBadge label="Test run" /> : null}
            <StatusBadge tone={runStatus(last.status)[0]} label={runStatus(last.status)[1]} />
          </>
        ) : (
          <span className="text-sm text-text-muted">No runs yet</span>
        )}
      </div>
    </li>
  );
}

/** "12 s" / "4 min" / "2 h" for the oldest waiting event. */
function age(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${Math.floor(seconds / 3600)} h`;
}

// DATA_PIPELINE §12, DDR-116 (10), (12): P2 landing is continuous; the backlog covers every region, so only
// a Central Administrator sees it (the backend refuses everyone else).
function BacklogPanel() {
  const global = useCan("pipelines.operate");
  const backlog = useBacklog(global);
  if (!global) return null;
  const state = queryState(backlog, { loading: "Loading outbox backlog…" });
  return (
    <section aria-labelledby="backlog" className="mt-3 rounded-panel border border-border bg-surface p-4">
      <h3 id="backlog" className="font-semibold">
        P2 event landing (outbox → raw)
      </h3>
      {state ?? (backlog.data ? <BacklogFigures b={backlog.data} /> : null)}
    </section>
  );
}

function BacklogFigures({ b }: { b: Backlog }) {
  const late = b.oldest_age_seconds !== null && b.oldest_age_seconds > b.warn_after_seconds;
  return (
    <>
      <dl className="mt-2 grid gap-3 text-sm sm:grid-cols-4" data-testid="backlog">
        <div>
          <dt className="text-text-muted">Waiting</dt>
          <dd className="text-xl font-semibold">{b.waiting}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Oldest waiting</dt>
          <dd className="text-xl font-semibold">
            {b.oldest_age_seconds === null ? "—" : age(b.oldest_age_seconds)}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Landed</dt>
          <dd className="text-xl font-semibold">{b.landed}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Rejected (kept)</dt>
          <dd className="text-xl font-semibold">{b.rejected}</dd>
        </div>
      </dl>
      {late ? (
        <p className="mt-2">
          <StatusBadge tone="warning" label={`Backlog older than ${age(b.warn_after_seconds)}`} />
        </p>
      ) : null}
      <p className="mt-2 text-xs text-text-muted">
        Warning after {age(b.warn_after_seconds)}
        {b.warn_is_test_default ? " (test default, not a final value)" : ""}. The dbt run (staging, core,
        marts, tests) comes with Task 12B.
      </p>
    </>
  );
}
