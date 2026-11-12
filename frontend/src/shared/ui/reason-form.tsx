import { useId, useState, type FormEvent } from "react";

import { Button } from "./button";

/**
 * Inline confirmation with a required reason or note (DDR-108). The backend validates again and
 * records the text in the audit trail; this form only checks the length for usability.
 */
export function ReasonForm({
  label,
  confirmLabel,
  minLength = 3,
  maxLength = 500,
  onConfirm,
  onCancel,
  hint,
}: {
  label: string;
  confirmLabel: string;
  minLength?: number;
  maxLength?: number;
  onConfirm: (text: string) => Promise<void>;
  onCancel: () => void;
  hint?: string;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (value.length < minLength) {
      setError(`Enter at least ${minLength} characters.`);
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await onConfirm(value);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-3 space-y-2 rounded-panel border border-border bg-muted p-3"
      noValidate
    >
      <label htmlFor={`${id}-text`} className="block text-sm font-medium">
        {label}
      </label>
      <textarea
        id={`${id}-text`}
        value={text}
        maxLength={maxLength}
        rows={2}
        onChange={(e) => setText(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={`${id}-hint ${id}-error`}
        className="w-full rounded-control border border-border bg-surface px-3 py-2"
      />
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-text-muted">
          {hint}
        </p>
      ) : null}
      <p id={`${id}-error`} role={error ? "alert" : undefined} className="text-sm">
        {error}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>
          {confirmLabel}
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
