import { ImageOff } from "lucide-react";

import { cn } from "@/shared/utils/cn";

// No logo has been supplied (DDR-08): a text wordmark, visibly labelled as a placeholder (CU-U5).
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="text-lg font-bold tracking-tight">DeliverIQ</span>
      <span className="rounded-control border border-current px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase">
        Placeholder logo
      </span>
    </span>
  );
}

// No image assets have been supplied (DDR-47).
export function ImageUnavailable({ className }: { className?: string }) {
  return (
    <div
      role="img"
      aria-label="Image unavailable"
      className={cn(
        "flex aspect-video items-center justify-center gap-2 rounded-panel bg-muted text-text-muted",
        className,
      )}
    >
      <ImageOff className="size-5" aria-hidden="true" />
      <span className="text-sm">Image unavailable</span>
    </div>
  );
}
