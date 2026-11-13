import { useState } from "react";

import { useKitchenSettings, useUpdateSettings, type KitchenMode, type KitchenSettings } from "../api";
import { refusalText } from "../format";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { queryState } from "@/shared/ui/query-state";
import { ReasonForm } from "@/shared/ui/reason-form";

const MODES: { value: KitchenMode; label: string; hint: string }[] = [
  { value: "NORMAL", label: "Normal", hint: "Accept up to the normal capacity" },
  { value: "BUSY", label: "Busy", hint: "Accept up to the lower Busy capacity" },
  { value: "PAUSED", label: "Paused", hint: "Accept no new orders; accepted orders continue" },
];

// KI-12–KI-15, DDR-111 (14): mode and capacity, KM only, with a reason; DDR-42 test defaults labelled.
export function KitchenSettingsPage() {
  const settings = useKitchenSettings();
  const state = queryState(settings, { loading: "Loading settings…" });
  if (state) return state;
  if (!settings.data) return null;
  return <SettingsForm key={settings.dataUpdatedAt} current={settings.data} />;
}

function SettingsForm({ current }: { current: KitchenSettings }) {
  const update = useUpdateSettings();
  const [mode, setMode] = useState<KitchenMode>(current.mode);
  const [normal, setNormal] = useState(String(current.normal_capacity.value));
  const [busy, setBusy] = useState(String(current.busy_capacity.value));
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const changed =
    mode !== current.mode ||
    normal !== String(current.normal_capacity.value) ||
    busy !== String(current.busy_capacity.value);

  function review() {
    setDone(null);
    const n = Number(normal);
    const b = Number(busy);
    if (!Number.isInteger(n) || !Number.isInteger(b) || n < 1 || b < 1 || n > 50 || b > 50) {
      setError("Capacities must be whole numbers from 1 to 50.");
      return;
    }
    if (b > n) {
      setError("Busy capacity cannot be higher than normal capacity.");
      return;
    }
    setError(null);
    setConfirming(true);
  }

  return (
    <section className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Settings · {current.kitchen_name}</h1>
      <fieldset className="rounded-panel border border-border bg-surface p-4">
        <legend className="px-1 font-semibold">Mode</legend>
        {MODES.map((m) => (
          <label key={m.value} className="flex min-h-11 items-center gap-3">
            <input
              type="radio"
              name="mode"
              className="size-5"
              checked={mode === m.value}
              onChange={() => setMode(m.value)}
            />
            <span>
              <span className="font-medium">{m.label}</span> ·{" "}
              <span className="text-sm text-text-muted">{m.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <Capacity
          id="normal"
          label="Normal capacity (orders)"
          value={normal}
          onChange={setNormal}
          testDefault={current.normal_capacity.is_test_default}
        />
        <Capacity
          id="busy"
          label="Busy capacity (orders)"
          value={busy}
          onChange={setBusy}
          testDefault={current.busy_capacity.is_test_default}
        />
      </div>
      {current.acceptance_timeout_minutes ? (
        <p className="text-sm text-text-muted">
          Acceptance timeout: {current.acceptance_timeout_minutes.value} min
          {current.acceptance_timeout_minutes.is_test_default ? " (test default, not final)" : ""}. It only
          marks incoming orders Overdue.
        </p>
      ) : null}
      {current.can_change ? (
        confirming ? (
          <ReasonForm
            label="Why are you changing the kitchen settings?"
            confirmLabel="Save settings"
            hint="Recorded in the audit log with your name."
            onCancel={() => setConfirming(false)}
            onConfirm={async (reason) => {
              try {
                await update.mutateAsync({
                  mode,
                  normal_capacity: Number(normal),
                  busy_capacity: Number(busy),
                  reason,
                });
                setConfirming(false);
                setDone("Settings saved.");
              } catch (e) {
                throw new Error(refusalText(e), { cause: e });
              }
            }}
          />
        ) : (
          <Button onClick={review} disabled={!changed}>
            Review and save
          </Button>
        )
      ) : (
        <p className="text-sm">Only the Kitchen Manager can change these settings.</p>
      )}
      {error ? (
        <p role="alert" className="text-sm">
          {error}
        </p>
      ) : null}
      {done ? <p role="status">{done}</p> : null}
    </section>
  );
}

function Capacity({
  id,
  label,
  value,
  onChange,
  testDefault,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  testDefault: boolean;
}) {
  return (
    <div>
      <label htmlFor={`cap-${id}`} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={`cap-${id}`}
        inputMode="numeric"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))}
        className={`mt-1 w-32 ${INPUT}`}
        aria-describedby={`cap-${id}-note`}
      />
      <p id={`cap-${id}-note`} className="mt-1 text-xs text-text-muted">
        {testDefault ? "Test default, not a final value (DDR-42 open)" : "Configured value"}
      </p>
    </div>
  );
}
