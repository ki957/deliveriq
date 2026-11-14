import { useId, useState } from "react";

import { useP2Status, useSetP2Schedule, type P2Status } from "../api";
import { actionError } from "@/shared/api/errors";
import { useCan } from "@/shared/auth/require-permission";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";
import { formatDateTime } from "@/shared/utils/format";

// DATA_PIPELINE §12; DDR-116 (7)–(10): freshness for every viewer; the optional timer for the CA only.
export function P2StatusPanel() {
  const status = useP2Status(true);
  const state = queryState(status, { loading: "Loading P2 status…" });
  return (
    <section aria-labelledby="p2-status" className="mt-4 rounded-panel border border-border bg-surface p-4">
      <h2 id="p2-status" className="text-lg font-semibold">
        Analytics freshness and schedule
      </h2>
      {state ?? (status.data ? <Figures s={status.data} /> : null)}
    </section>
  );
}

function Figures({ s }: { s: P2Status }) {
  const canOperate = useCan("pipelines.operate");
  return (
    <div className="mt-2 space-y-3 text-sm">
      <p data-testid="freshness">
        Real marts fresh as of:{" "}
        <span className="font-medium">
          {s.freshness ? formatDateTime(s.freshness.fresh_as_of) : "never built"}
        </span>
        . Freshness is published only when every critical dbt test passed.
      </p>
      <p className="rounded-control border border-dashed border-border p-2" data-testid="real-marts-note">
        Real marts use real events only. Every order in this POC is a TEST order, so the real marts are empty;
        each run counts the TEST events it left out. Labelled simulated data comes with Task 14.
      </p>
      <p data-testid="schedule">
        Schedule: <span className="font-medium">{s.schedule.enabled ? "on" : "off"}</span>, every{" "}
        {s.schedule.interval_minutes} min
        {s.schedule.interval_is_test_default ? " (test default, not a final value)" : ""}.
      </p>
      {canOperate ? <ScheduleForm s={s} /> : null}
    </div>
  );
}

function ScheduleForm({ s }: { s: P2Status }) {
  const save = useSetP2Schedule();
  const id = useId();
  const [enabled, setEnabled] = useState(s.schedule.enabled);
  const [interval, setInterval] = useState(s.schedule.interval_minutes);
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const changed = enabled !== s.schedule.enabled || interval !== s.schedule.interval_minutes;
  return (
    <div className="space-y-2 rounded-control bg-muted p-3">
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          className="size-5"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Run P2 on a timer
      </label>
      <div>
        <label htmlFor={`${id}-interval`} className="block font-medium">
          Every
        </label>
        <select
          id={`${id}-interval`}
          value={interval}
          onChange={(e) => setInterval(Number(e.target.value))}
          className={`mt-1 ${INPUT}`}
        >
          {s.intervals.map((m) => (
            <option key={m} value={m}>
              {m} minutes
            </option>
          ))}
        </select>
      </div>
      {confirming ? (
        <ReasonForm
          label="Why are you changing the P2 schedule?"
          confirmLabel="Save schedule"
          hint="Recorded in the audit log with your name."
          onCancel={() => setConfirming(false)}
          onConfirm={async (reason) => {
            try {
              await save.mutateAsync({ enabled, interval_minutes: interval, reason });
              setConfirming(false);
              setDone("Schedule saved.");
            } catch (e) {
              throw new Error(actionError(e), { cause: e });
            }
          }}
        />
      ) : (
        <Button
          variant="secondary"
          disabled={!changed}
          onClick={() => {
            setDone(null);
            setConfirming(true);
          }}
        >
          Review and save
        </Button>
      )}
      {done ? <p role="status">{done}</p> : null}
    </div>
  );
}
