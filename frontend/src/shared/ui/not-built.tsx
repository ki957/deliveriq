import { Construction } from "lucide-react";

// Honest placeholder for screens owned by later tasks or blocked by an open decision (DDR-100, KI-U6,
// DDR-114 (2)): no fake data or controls. `reason` says why the screen is not built.
export function NotBuilt({
  title,
  task,
  reason,
}: {
  title: string;
  task?: number | undefined;
  reason?: string | undefined;
}) {
  return (
    <section className="mx-auto my-10 max-w-xl rounded-panel border border-dashed border-border bg-surface p-6">
      <div className="flex items-center gap-3">
        <Construction className="size-6 shrink-0 text-text-muted" aria-hidden="true" />
        <h1 className="text-xl font-semibold">{title}</h1>
      </div>
      <p className="mt-3 font-medium">Not built yet</p>
      <p className="mt-1 text-sm text-text-muted">
        {reason
          ? reason
          : task
            ? `This screen is planned in Task ${task} of the build plan.`
            : "This screen is planned in a later task."}{" "}
        Nothing on this page is live.
      </p>
    </section>
  );
}
