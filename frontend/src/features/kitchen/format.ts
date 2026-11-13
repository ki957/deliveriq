import type { StatusTone } from "@/shared/ui/status-badge";

import { KitchenRefusal, type KitchenOrder } from "./api";

// DDR-112 (9): the ingredient's own unit, up to 3 decimals, trailing zeros trimmed.
export function formatQty(value: string | number | null | undefined, unit: string): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return `${n.toLocaleString("en-IN", { maximumFractionDigits: 3 })} ${unit}`;
}

// KI-U4, DDR-112 (7): Preparing blue, Ready green, Rejected red, Incoming and Accepted neutral.
export function statusTone(status: KitchenOrder["fulfilment_status"]): StatusTone {
  if (status === "PREPARING") return "info";
  if (status === "READY_FOR_PICKUP") return "success";
  if (status === "REJECTED" || status === "CANCELLED") return "danger";
  return "neutral";
}

export function minutesSince(iso: string | null | undefined, now: number): number | null {
  if (!iso) return null;
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

const REFUSALS: Record<string, string> = {
  kitchen_paused: "The kitchen is Paused: no new orders can be accepted. Change the mode in Settings.",
  kitchen_at_capacity: "The kitchen is at capacity. Finish or hand over an order first.",
  recipe_not_active: "A dish in this order has no active recipe version, so it cannot be accepted.",
  stock_short: "Not enough stock to accept this order.",
};

/** Customer-free wording for kitchen refusals (DDR-111 (3), (4)). */
export function refusalText(error: unknown): string {
  if (!(error instanceof KitchenRefusal)) return "Something went wrong. Try again.";
  if (error.status === 403) return "You don't have permission for this action.";
  if (error.status === 404) return "This order no longer exists or is outside your kitchen.";
  const base = REFUSALS[error.code] ?? error.message;
  const shortages = error.body.shortages;
  if (error.code === "stock_short" && Array.isArray(shortages)) {
    const lines = shortages
      .map((s) => s as { ingredient?: string; unit?: string; needed?: string; available?: string })
      .map(
        (s) =>
          `${s.ingredient}: needs ${formatQty(s.needed, s.unit ?? "")}, ${formatQty(s.available, s.unit ?? "")} available`,
      );
    return `${base} ${lines.join("; ")}.`;
  }
  return base;
}
