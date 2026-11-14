import { useRealtimeStatus } from "@/shared/realtime/use-live";

/**
 * DDR-112 (5), DDR-115 (8): says whether the page updates live or by polling, with the last refresh time.
 */
export function PollNote({ updatedAt }: { updatedAt: number }) {
  const status = useRealtimeStatus();
  const time = updatedAt
    ? new Date(updatedAt).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
  return (
    <p className="text-xs text-text-muted" data-testid="poll-note" data-live={status === "live"}>
      {status === "live" ? "Live" : "Live updates paused · updates every 10 s"} · last updated {time}
    </p>
  );
}
