import { useCallback, useSyncExternalStore } from "react";

// A visitor's chosen location lives in this browser only; nothing is stored on the server (DDR-110 (8)).
export interface ChosenLocation {
  lat: number;
  lng: number;
  label: string;
  source: "gps" | "manual" | "address";
  addressId?: string;
}

const KEY = "diq.customer.location";
const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedValue: ChosenLocation | null = null;

function read(): ChosenLocation | null {
  const raw = globalThis.localStorage?.getItem(KEY) ?? null;
  if (raw === cachedRaw) return cachedValue;
  cachedRaw = raw;
  try {
    const parsed = raw ? (JSON.parse(raw) as ChosenLocation) : null;
    cachedValue = parsed && Number.isFinite(parsed.lat) && Number.isFinite(parsed.lng) ? parsed : null;
  } catch {
    cachedValue = null;
  }
  return cachedValue;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useChosenLocation(): [ChosenLocation | null, (next: ChosenLocation | null) => void] {
  const value = useSyncExternalStore(subscribe, read, () => null);
  const set = useCallback((next: ChosenLocation | null) => {
    if (next) globalThis.localStorage?.setItem(KEY, JSON.stringify(next));
    else globalThis.localStorage?.removeItem(KEY);
    listeners.forEach((l) => l());
  }, []);
  return [value, set];
}
