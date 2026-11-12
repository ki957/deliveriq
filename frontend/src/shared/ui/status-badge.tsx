import { AlertOctagon, CheckCircle2, Circle, Clock, Info } from "lucide-react";

import { cn } from "@/shared/utils/cn";

// Status is always text + icon + colour, never colour alone (SH-03, PL-18).
export type StatusTone = "info" | "success" | "warning" | "danger" | "neutral";

const TONES: Record<StatusTone, { className: string; Icon: typeof Info }> = {
  info: { className: "bg-status-info", Icon: Info },
  success: { className: "bg-status-success", Icon: CheckCircle2 },
  warning: { className: "bg-status-warning", Icon: Clock },
  danger: { className: "bg-status-danger", Icon: AlertOctagon },
  neutral: { className: "bg-status-neutral", Icon: Circle },
};

export function StatusBadge({ tone, label }: { tone: StatusTone; label: string }) {
  const { className, Icon } = TONES[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-control px-2 py-1 text-xs font-semibold text-white",
        className,
      )}
      data-tone={tone}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}
