import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";

import { realtime, type Status } from "./connection";

// Mutations refetch in the background (`void invalidateQueries`), so a burst of hints never delays an
// action's own success message.
export const BURST_MS = 250;

/** The tab's socket status (for labels): "live", "connecting" or "offline". */
export function useRealtimeStatus(): Status {
  return useSyncExternalStore(realtime.onStatus, realtime.getStatus, () => "offline" as const);
}

/**
 * Subscribe to topics and refetch `queryKeys` on every hint and on (re)subscription. Returns true while
 * every topic is confirmed live; callers poll as before when it is false (DDR-115 (8)).
 */
export function useLiveRefresh(topics: readonly string[], queryKeys: readonly QueryKey[]): boolean {
  const client = useQueryClient();
  const topicKey = [...new Set(topics)].sort().join("|");
  const keysKey = JSON.stringify(queryKeys);
  useEffect(() => {
    if (!topicKey) return;
    const keys = JSON.parse(keysKey) as QueryKey[];
    // One transaction can send many hints (e.g. one per stock row): refetch once per burst.
    let timer: ReturnType<typeof setTimeout> | null = null;
    const refresh = () => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        for (const queryKey of keys) void client.invalidateQueries({ queryKey });
      }, BURST_MS);
    };
    const offs = topicKey.split("|").map((t) => realtime.subscribe(t, refresh));
    return () => {
      if (timer) clearTimeout(timer);
      offs.forEach((off) => off());
    };
  }, [client, topicKey, keysKey]);
  const live = useSyncExternalStore(
    realtime.onStatus,
    () => topicKey !== "" && topicKey.split("|").every((t) => realtime.isLive(t)),
    () => false,
  );
  return live;
}
