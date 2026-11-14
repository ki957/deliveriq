/** DDR-112 (5): polling is labelled with the last refresh time (until realtime, Task 11). */
export function PollNote({ updatedAt }: { updatedAt: number }) {
  const time = updatedAt
    ? new Date(updatedAt).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
  return (
    <p className="text-xs text-text-muted" data-testid="poll-note">
      Updates every 10 s · last updated {time}
    </p>
  );
}
