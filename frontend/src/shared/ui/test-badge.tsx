import { FlaskConical } from "lucide-react";

// Every TEST fixture and test run is labelled in every UI (plan §5.2, §6): text + icon, never colour alone.
export function TestBadge({ label = "Test data" }: { label?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-control border border-status-warning px-2 py-0.5 text-xs font-semibold text-text"
      data-testid="test-badge"
    >
      <FlaskConical className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}
