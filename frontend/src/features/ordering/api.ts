import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

type S = components["schemas"];
export type MenuItem = S["CustomerMenuItemOut"];
export type Dish = S["DishDetailOut"];
export type MenuFilters = S["MenuFiltersOut"];
export type Serviceability = S["ServiceabilityOut"];
export type Address = S["AddressOut"];
export type Cart = S["CartOut"];
export type CartLine = S["CartLineOut"];
export type Order = S["OrderOut"];
export type PaymentMethod = S["OrderCreateIn"]["payment_method"];
export type SimOutcome = S["SimulateIn"]["outcome"];

export interface MenuQuery {
  q?: string;
  category?: string;
  veg?: boolean;
  spice?: string;
  max_price_paise?: number;
  bestseller?: boolean;
}

export const keys = {
  menu: (q: MenuQuery) => ["ordering", "menu", q] as const,
  filters: ["ordering", "filters"] as const,
  dish: (id: string) => ["ordering", "dish", id] as const,
  reach: (lat: number, lng: number) => ["ordering", "serviceability", lat, lng] as const,
  addresses: ["ordering", "addresses"] as const,
  cart: (addressId: string | null, coupon: string | null) => ["ordering", "cart", addressId, coupon] as const,
  orders: ["ordering", "orders"] as const,
  order: (id: string) => ["ordering", "order", id] as const,
};

// ---------------------------------------------------------------- public reads
export function useMenu(query: MenuQuery, enabled: boolean) {
  return useQuery({
    queryKey: keys.menu(query),
    queryFn: async () => unwrap(await api.GET("/api/v1/menu/items", { params: { query } })),
    enabled,
  });
}

export function useMenuFilters(enabled: boolean) {
  return useQuery({
    queryKey: keys.filters,
    queryFn: async () => unwrap(await api.GET("/api/v1/menu/filters")),
    enabled,
  });
}

export function useDish(id: string) {
  return useQuery({
    queryKey: keys.dish(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/menu/items/{item_id}", { params: { path: { item_id: id } } })),
  });
}

export function useServiceability(point: { lat: number; lng: number } | null) {
  return useQuery({
    queryKey: keys.reach(point?.lat ?? 0, point?.lng ?? 0),
    queryFn: async () => {
      if (!point) throw new Error("No location chosen");
      return unwrap(
        await api.GET("/api/v1/serviceability", { params: { query: { lat: point.lat, lng: point.lng } } }),
      );
    },
    enabled: point !== null,
  });
}

// ---------------------------------------------------------------- addresses (signed in)
export function useAddresses(enabled: boolean) {
  return useQuery({
    queryKey: keys.addresses,
    queryFn: async () => unwrap(await api.GET("/api/v1/me/addresses")),
    enabled,
  });
}

export function useAddAddress() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: S["AddressIn"]) => unwrap(await api.POST("/api/v1/me/addresses", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["ordering"] }),
  });
}

// ---------------------------------------------------------------- cart (persisted, CU-11)
export function useCart(addressId: string | null, coupon: string | null) {
  return useQuery({
    queryKey: keys.cart(addressId, coupon),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/cart", {
          params: {
            query: {
              ...(addressId ? { address_id: addressId } : {}),
              ...(coupon ? { coupon_code: coupon } : {}),
            },
          },
        }),
      ),
  });
}

/** Refusals carry a stable `code` (DDR-110); the UI words them in `messages.ts`. */
export class Refusal extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly body: Record<string, unknown>,
  ) {
    super(message);
  }
}

function refusal(result: { error?: unknown; response: Response }): Refusal {
  const body = (result.error ?? {}) as Record<string, unknown>;
  return new Refusal(
    result.response.status,
    String(body.code ?? `http_${result.response.status}`),
    String(body.message ?? body.detail ?? "Request failed"),
    body,
  );
}

function useCartMutation<A>(run: (arg: A) => Promise<{ data?: Cart; error?: unknown; response: Response }>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (arg: A) => {
      const result = await run(arg);
      if (!result.response.ok || !result.data) throw refusal(result);
      return result.data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["ordering", "cart"] }),
  });
}

export function useSetQuantity() {
  return useCartMutation(({ id, quantity }: { id: string; quantity: number }) =>
    api.PUT("/api/v1/cart/items/{menu_item_id}", {
      params: { path: { menu_item_id: id } },
      body: { quantity },
    }),
  );
}

export function useRemoveLine() {
  return useCartMutation((id: string) =>
    api.DELETE("/api/v1/cart/items/{menu_item_id}", { params: { path: { menu_item_id: id } } }),
  );
}

export function useAcceptPrice() {
  return useCartMutation((id: string) =>
    api.POST("/api/v1/cart/items/{menu_item_id}/accept-price", { params: { path: { menu_item_id: id } } }),
  );
}

export function useRemoveUnavailable() {
  // The argument records the customer's explicit confirmation (CU-14).
  return useCartMutation((confirmed: true) => {
    if (!confirmed) throw new Error("Removal needs confirmation");
    return api.POST("/api/v1/cart/remove-unavailable");
  });
}

// ---------------------------------------------------------------- orders
export function usePlaceOrder() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, body }: { key: string; body: S["OrderCreateIn"] }) => {
      const result = await api.POST("/api/v1/orders", {
        params: { header: { "Idempotency-Key": key } },
        body,
      });
      if (!result.response.ok || !result.data) throw refusal(result);
      return result.data;
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["ordering"] }),
  });
}

export function useOrders() {
  return useQuery({ queryKey: keys.orders, queryFn: async () => unwrap(await api.GET("/api/v1/orders")) });
}

export function useOrder(id: string) {
  return useQuery({
    queryKey: keys.order(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })),
    // While the order is on its way, refresh the code and position (DDR-113 (8); realtime is Task 11).
    refetchInterval: (query) => (query.state.data?.fulfilment_status === "OUT_FOR_DELIVERY" ? 10_000 : false),
    refetchIntervalInBackground: false,
  });
}

export function useSimulatePayment(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (outcome: SimOutcome) => {
      const result = await api.POST("/api/v1/orders/{order_id}/payment/simulate", {
        params: { path: { order_id: id } },
        body: { outcome },
      });
      if (!result.response.ok || !result.data) throw refusal(result);
      return result.data;
    },
    onSuccess: (order) => client.setQueryData(keys.order(id), order),
  });
}

export function useCancelOrder(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = await api.POST("/api/v1/orders/{order_id}/cancel", {
        params: { path: { order_id: id } },
      });
      if (!result.response.ok || !result.data) throw refusal(result);
      return result.data;
    },
    onSuccess: (order) => client.setQueryData(keys.order(id), order),
  });
}
