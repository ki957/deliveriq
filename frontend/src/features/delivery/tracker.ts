import { useSyncExternalStore } from "react";

import { sendPoints, type PointIn } from "./api";

// GPS session for the open delivery (DL-G1–DL-G4; DDR-52, DDR-113 (8), (9), (19), (20)).
// Foreground only (no background GPS, DDR-15). Points are buffered in memory (at most 300, oldest
// dropped) and re-sent on reconnect; the backend refuses stale or out-of-order points. Nothing is queued
// except location points: actions are blocked offline.

export const BUFFER_MAX = 300;
export const SEND_EVERY_MS = 5_000;
export const SIM_STEP_M = 15; // DDR-113 (19): 15 m per point, one point every 5 s (about 11 km/h)
const BATCH_MAX = 100;

export type Mode = "REAL" | "SIMULATED";
export type GpsState = {
  mode: Mode | null;
  // "denied" and "unavailable" never produce a position (DL-G3).
  status: "idle" | "waiting" | "ok" | "denied" | "unavailable";
  accuracyM: number | null;
  last: { lat: number; lng: number } | null;
  buffered: number;
  dropped: number;
  online: boolean;
  lastSentAt: number | null;
};

type Place = { lat: number; lng: number };
type Route = { from: Place; to: Place | null; moving: boolean };

let state: GpsState = {
  mode: null,
  status: "idle",
  accuracyM: null,
  last: null,
  buffered: 0,
  dropped: 0,
  online: typeof navigator === "undefined" ? true : navigator.onLine,
  lastSentAt: null,
};
const listeners = new Set<() => void>();
let buffer: PointIn[] = [];
let watchId: number | null = null;
let timer: ReturnType<typeof setInterval> | null = null;
let route: Route | null = null;
let sending = false;

function set(patch: Partial<GpsState>) {
  state = { ...state, ...patch, buffered: buffer.length };
  listeners.forEach((l) => l());
}

export function useGps(): GpsState {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
    () => state,
  );
}

export function push(point: PointIn) {
  buffer.push(point);
  let dropped = state.dropped;
  while (buffer.length > BUFFER_MAX) {
    buffer.shift();
    dropped += 1;
  }
  set({ last: { lat: point.lat, lng: point.lng }, dropped });
}

export async function flush(): Promise<void> {
  if (sending || buffer.length === 0 || !state.online) return;
  sending = true;
  const batch = buffer.slice(0, BATCH_MAX);
  try {
    await sendPoints(batch);
    buffer = buffer.slice(batch.length); // accepted or refused as stale: either way, never re-sent
    set({ lastSentAt: Date.now() });
  } catch {
    set({ online: typeof navigator === "undefined" ? false : navigator.onLine }); // keep the buffer
  } finally {
    sending = false;
  }
}

/** One step of the simulated route (DDR-113 (9), (19)): a straight line, 15 m per point. */
export function step(from: Place, to: Place, metres: number): Place {
  const dLat = (to.lat - from.lat) * 111_320;
  const dLng = (to.lng - from.lng) * 111_320 * Math.cos((from.lat * Math.PI) / 180);
  const distance = Math.hypot(dLat, dLng);
  if (distance <= metres || distance === 0) return to;
  const f = metres / distance;
  return { lat: from.lat + (to.lat - from.lat) * f, lng: from.lng + (to.lng - from.lng) * f };
}

function tick() {
  if (state.mode === "SIMULATED" && route) {
    const here = state.last ?? route.from;
    const next = route.moving && route.to ? step(here, route.to, SIM_STEP_M) : here;
    push({
      lat: next.lat,
      lng: next.lng,
      accuracy_m: null,
      recorded_at: new Date().toISOString(),
      source: "SIMULATED",
    });
    set({ status: "ok", accuracyM: null });
  }
  void flush();
}

function stopWatch() {
  if (watchId !== null && typeof navigator !== "undefined") navigator.geolocation?.clearWatch(watchId);
  watchId = null;
}

/** Start or keep the session for the open delivery; `moving` once the order is picked up. */
export function start(mode: Mode, next: Route) {
  route = next;
  if (state.mode === mode && timer) return;
  stopWatch();
  set({
    mode,
    status: mode === "SIMULATED" ? "ok" : "waiting",
    last: mode === "SIMULATED" ? next.from : null,
  });
  if (mode === "REAL") {
    if (!navigator.geolocation) {
      set({ status: "unavailable" });
    } else {
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          push({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy_m: Number.isFinite(pos.coords.accuracy)
              ? Math.round(pos.coords.accuracy * 100) / 100
              : null,
            recorded_at: new Date(pos.timestamp).toISOString(),
            source: "REAL",
          });
          set({ status: "ok", accuracyM: pos.coords.accuracy });
        },
        (err) => set({ status: err.code === err.PERMISSION_DENIED ? "denied" : "unavailable" }),
        { enableHighAccuracy: true, maximumAge: 5_000, timeout: 20_000 },
      );
    }
  }
  if (!timer) timer = setInterval(tick, SEND_EVERY_MS);
}

export function stop() {
  stopWatch();
  if (timer) clearInterval(timer);
  timer = null;
  route = null;
  void flush();
  set({ mode: null, status: "idle", accuracyM: null, last: null });
}

if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    set({ online: true });
    void flush();
  });
  window.addEventListener("offline", () => set({ online: false }));
}

/** Tests only: reset the module state. */
export function resetForTests() {
  stop();
  buffer = [];
  set({ dropped: 0, online: true, lastSentAt: null });
}
