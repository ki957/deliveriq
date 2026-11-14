import { useId, useState, type ReactNode } from "react";

import { type KitchenStatus } from "../api";
import { actionError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { INPUT } from "@/shared/ui/input";
import { PollNote } from "@/shared/ui/poll-note";
import { ReasonForm } from "@/shared/ui/reason-form";

export function PageHeader({
  title,
  updatedAt,
  children,
}: {
  title: string;
  updatedAt?: number | undefined;
  children?: ReactNode;
}) {
  return (
    <header className="space-y-1">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {updatedAt !== undefined ? <PollNote updatedAt={updatedAt} /> : null}
      {children}
    </header>
  );
}

/** A button that opens the inline reason form; every management action needs a reason (MG-03). */
export function ReasonAction({
  label,
  prompt,
  confirmLabel,
  onConfirm,
  variant = "secondary",
}: {
  label: string;
  prompt: string;
  confirmLabel: string;
  onConfirm: (reason: string) => Promise<unknown>;
  variant?: "primary" | "secondary";
}) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  if (open) {
    return (
      <ReasonForm
        label={prompt}
        confirmLabel={confirmLabel}
        hint="Recorded in the audit log with your name and role."
        onCancel={() => setOpen(false)}
        onConfirm={async (reason) => {
          try {
            await onConfirm(reason);
            setOpen(false);
            setDone(`${confirmLabel}: done.`);
          } catch (e) {
            throw new Error(actionError(e), { cause: e });
          }
        }}
      />
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button
        variant={variant}
        onClick={() => {
          setDone(null);
          setOpen(true);
        }}
      >
        {label}
      </Button>
      {done ? (
        <span role="status" className="text-sm">
          {done}
        </span>
      ) : null}
    </span>
  );
}

export function KitchenPicker({
  kitchens,
  value,
  onChange,
}: {
  kitchens: KitchenStatus[];
  value: string;
  onChange: (id: string) => void;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        Kitchen
      </label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={`mt-1 ${INPUT}`}>
        {kitchens.map((k) => (
          <option key={k.id} value={k.id}>
            {k.name} · {k.region_name}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th scope="col" className="p-2 font-medium">
      {children}
    </th>
  );
}

export function Td({ children }: { children: ReactNode }) {
  return <td className="p-2 align-top">{children}</td>;
}

export function TableBox({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-panel border border-border bg-surface">
      <table className="w-full text-left text-sm" aria-label={label}>
        {children}
      </table>
    </div>
  );
}

/** "Page 2 of 5 · 230 results" with previous/next (50 per page, DDR-114 (7)). */
export function Pager({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center gap-2 text-sm">
      <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span>
        Page {page} of {pages} · {total} {total === 1 ? "result" : "results"}
      </span>
      <Button variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </nav>
  );
}

/** `yyyy-mm-dd` (local date input) → ISO start or end of that day in IST (#15 §2). */
export function dayBound(day: string, end: boolean): string | undefined {
  if (!day) return undefined;
  return `${day}T${end ? "23:59:59" : "00:00:00"}+05:30`;
}
