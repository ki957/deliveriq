import { AlertTriangle, Inbox, Loader2, ShieldX } from "lucide-react";
import type { ReactNode } from "react";

// Loading, empty, error and permission-denied states for every screen (PL-17).
function Panel({
  icon,
  title,
  children,
  role,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  role: "status" | "alert";
}) {
  return (
    <section
      role={role}
      className="mx-auto my-10 max-w-lg rounded-panel border border-border bg-surface p-6 text-center"
    >
      <div className="mb-3 flex justify-center text-text-muted" aria-hidden="true">
        {icon}
      </div>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children ? <div className="mt-2 text-sm text-text-muted">{children}</div> : null}
    </section>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <Panel role="status" icon={<Loader2 className="size-6 animate-spin" />} title={label} />;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Panel role="status" icon={<Inbox className="size-6" />} title={title}>
      {children}
    </Panel>
  );
}

export function ErrorState({
  title = "Something went wrong",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <Panel role="alert" icon={<AlertTriangle className="size-6" />} title={title}>
      {children}
    </Panel>
  );
}

export function DeniedState({ children }: { children?: ReactNode }) {
  return (
    <Panel role="alert" icon={<ShieldX className="size-6" />} title="You don't have access to this area">
      {children}
    </Panel>
  );
}
