import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

type S = components["schemas"];
export type KitchenQueue = S["KitchenQueueOut"];
export type KitchenOrder = S["KitchenOrderOut"];
export type KitchenItem = S["KitchenItemOut"];
export type KitchenSettings = S["KitchenSettingsOut"];
export type KitchenMode = S["KitchenSettingsIn"]["mode"];
export type Stock = S["StockOut"];
export type KitchenDish = S["KitchenDishOut"];
export type AvailabilityRequest = S["AvailabilityRequestOut"];
export type AvailabilityKind = S["AvailabilityRequestIn"]["kind"];

// DDR-111 (13), DDR-112 (5): poll while the tab is visible until realtime (Task 11).
export const POLL_MS = 10_000;

const keys = {
  queue: ["kitchen", "queue"] as const,
  settings: ["kitchen", "settings"] as const,
  stock: ["kitchen", "stock"] as const,
  lowStock: ["kitchen", "low-stock"] as const,
  dishes: (kitchenId: string) => ["kitchen", "dishes", kitchenId] as const,
  requests: (pendingOnly: boolean) => ["kitchen", "availability", pendingOnly] as const,
};

/** A kitchen refusal keeps its stable `code` and details (e.g. `shortages`) for the UI. */
export class KitchenRefusal extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly body: Record<string, unknown>,
  ) {
    super(message);
  }
}

async function call<T>(run: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const result = await run;
  if (result.response.ok && result.data !== undefined) return result.data;
  const body = (result.error ?? {}) as Record<string, unknown>;
  throw new KitchenRefusal(
    result.response.status,
    String(body.code ?? `http_${result.response.status}`),
    String(body.message ?? body.detail ?? "Request failed"),
    body,
  );
}

// ---------------------------------------------------------------- queue and preparation
export function useKitchenQueue() {
  return useQuery({
    queryKey: keys.queue,
    queryFn: async () => unwrap(await api.GET("/api/v1/kitchen/orders")),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });
}

type Action =
  | { kind: "accept"; orderId: string }
  | { kind: "start"; orderId: string }
  | { kind: "reject"; orderId: string; reason: string }
  | { kind: "item"; orderId: string; itemId: string; status: "PREPARING" | "PREPARED" };

export function useKitchenAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (action: Action) => {
      const path = { params: { path: { order_id: action.orderId } } };
      switch (action.kind) {
        case "accept":
          return call(api.POST("/api/v1/kitchen/orders/{order_id}/accept", path));
        case "start":
          return call(api.POST("/api/v1/kitchen/orders/{order_id}/start", path));
        case "reject":
          return call(
            api.POST("/api/v1/kitchen/orders/{order_id}/reject", {
              ...path,
              body: { reason: action.reason },
            }),
          );
        case "item":
          return call(
            api.POST("/api/v1/kitchen/orders/{order_id}/items/{item_id}/status", {
              params: { path: { order_id: action.orderId, item_id: action.itemId } },
              body: { status: action.status },
            }),
          );
      }
    },
    // Refresh at once after every action (DDR-112 (5)); stock and alerts may have changed too.
    onSettled: () => client.invalidateQueries({ queryKey: ["kitchen"] }),
  });
}

// ---------------------------------------------------------------- settings (KM)
export function useKitchenSettings() {
  return useQuery({
    queryKey: keys.settings,
    queryFn: async () => unwrap(await api.GET("/api/v1/kitchen/settings")),
  });
}

export function useUpdateSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: S["KitchenSettingsIn"]) => call(api.PUT("/api/v1/kitchen/settings", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["kitchen"] }),
  });
}

// ---------------------------------------------------------------- inventory
export function useStock(enabled: boolean) {
  return useQuery({
    queryKey: keys.stock,
    queryFn: async () => unwrap(await api.GET("/api/v1/kitchen/inventory")),
    enabled,
  });
}

export function useLowStock() {
  return useQuery({
    queryKey: keys.lowStock,
    queryFn: async () => unwrap(await api.GET("/api/v1/kitchen/inventory/low-stock")),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });
}

export function useAdjustStock() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      ingredientId,
      delta,
      reason,
    }: {
      ingredientId: string;
      delta: string;
      reason: string;
    }) =>
      call(
        api.POST("/api/v1/kitchen/inventory/{ingredient_id}/adjust", {
          params: { path: { ingredient_id: ingredientId } },
          body: { delta, reason },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["kitchen"] }),
  });
}

export function useSetThreshold() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      ingredientId,
      threshold,
      reason,
    }: {
      ingredientId: string;
      threshold: string | null;
      reason: string;
    }) =>
      call(
        api.PUT("/api/v1/kitchen/inventory/{ingredient_id}/threshold", {
          params: { path: { ingredient_id: ingredientId } },
          body: { low_stock_threshold: threshold, reason },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["kitchen"] }),
  });
}

// ---------------------------------------------------------------- dish availability (KI-24; DDR-111 (7))
export function useKitchenDishes(kitchenId: string | undefined) {
  return useQuery({
    queryKey: keys.dishes(kitchenId ?? ""),
    queryFn: async () => {
      if (!kitchenId) throw new Error("No kitchen");
      return unwrap(
        await api.GET("/api/v1/menu/availability/dishes", { params: { query: { kitchen_id: kitchenId } } }),
      );
    },
    enabled: Boolean(kitchenId),
  });
}

export function useAvailabilityRequests(pendingOnly = false) {
  return useQuery({
    queryKey: keys.requests(pendingOnly),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/menu/availability/requests", {
          params: { query: { pending_only: pendingOnly } },
        }),
      ),
  });
}

export function useRequestAvailability() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: S["AvailabilityRequestIn"]) =>
      call(api.POST("/api/v1/menu/availability/requests", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["kitchen"] }),
  });
}

export function useDecideAvailability() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, approve, reason }: { id: string; approve: boolean; reason: string | null }) =>
      call(
        api.POST("/api/v1/menu/availability/requests/{request_id}/decision", {
          params: { path: { request_id: id } },
          body: { approve, reason },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["kitchen"] }),
  });
}
