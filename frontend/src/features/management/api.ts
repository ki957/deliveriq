import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

type S = components["schemas"];
export type Overview = S["OverviewOut"];
export type KitchenStatus = S["KitchenStatusOut"];
export type Region = S["RegionOut"];
export type OrderRow = S["OrderRowOut"];
export type OrderPage = S["OrderPageOut"];
export type OrderDetail = S["OrderDetailOut"];
export type Delivery = S["DeliveryOut"];
export type Refunds = S["RefundsOut"];
export type Inventory = S["InventoryOut"];
export type AuditPage = S["AuditPageOut"];
export type AuditRow = S["AuditOut"];
export type Staff = S["StaffOut"];
export type StaffIn = S["StaffIn"];
export type Agent = S["AgentOut"];

// DDR-112 (5) pattern: poll while the tab is visible until realtime (Task 11).
export const POLL_MS = 10_000;
const poll = { refetchInterval: POLL_MS, refetchIntervalInBackground: false } as const;

// Fulfilment statuses with their Management labels (Matrix §7.3; backend `orders.domain._LABELS`).
export const ORDER_STATUSES: { value: string; label: string }[] = [
  { value: "PLACED", label: "Placed" },
  { value: "PENDING_KITCHEN", label: "Awaiting kitchen" },
  { value: "ACCEPTED", label: "Accepted" },
  { value: "PREPARING", label: "Preparing" },
  { value: "READY_FOR_PICKUP", label: "Ready" },
  { value: "PICKED_UP", label: "Picked up" },
  { value: "OUT_FOR_DELIVERY", label: "Out for delivery" },
  { value: "DELIVERED", label: "Delivered" },
  { value: "CANCELLED", label: "Cancelled" },
  { value: "REJECTED", label: "Rejected" },
  { value: "DELIVERY_FAILED", label: "Delivery failed" },
];

export type OrderFilters = {
  status?: string | undefined;
  kitchen_id?: string | undefined;
  agent_id?: string | undefined;
  exception?: boolean | undefined;
  date_from?: string | undefined;
  date_to?: string | undefined;
};

export type AuditFilters = {
  action?: string | undefined;
  target_type?: string | undefined;
  actor_role?: string | undefined;
  date_from?: string | undefined;
  date_to?: string | undefined;
};

/** Only the filters that are set, so the query string matches the screen exactly. */
export function cleanFilters<T extends Record<string, unknown>>(
  filters: T,
): { [K in keyof T]?: Exclude<T[K], undefined> } {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== "")) as {
    [K in keyof T]?: Exclude<T[K], undefined>;
  };
}

/** Same-origin CSV link with the current filters (DDR-114 (8)); the server enforces scope and limits. */
export function csvHref(path: "orders.csv" | "audit.csv", filters: Record<string, unknown>): string {
  const query = new URLSearchParams(
    Object.entries(cleanFilters(filters)).map(([k, v]) => [k, String(v)]),
  ).toString();
  return `/api/v1/management/${path}${query ? `?${query}` : ""}`;
}

export const keys = {
  all: ["management"] as const,
  overview: ["management", "overview"] as const,
  regions: ["management", "regions"] as const,
  kitchens: ["management", "kitchens"] as const,
  orders: (page: number, f: OrderFilters) => ["management", "orders", page, f] as const,
  order: (id: string) => ["management", "order", id] as const,
  deliveries: ["management", "deliveries"] as const,
  agents: ["management", "agents"] as const,
  refunds: ["management", "refunds"] as const,
  inventory: (kitchenId: string) => ["management", "inventory", kitchenId] as const,
  audit: (page: number, f: AuditFilters) => ["management", "audit", page, f] as const,
  staff: ["management", "staff"] as const,
};

// ---------------------------------------------------------------- reads
export function useOverview() {
  return useQuery({
    queryKey: keys.overview,
    queryFn: async () => unwrap(await api.GET("/api/v1/management/overview")),
    ...poll,
  });
}

export function useRegions() {
  return useQuery({
    queryKey: keys.regions,
    queryFn: async () => unwrap(await api.GET("/api/v1/management/regions")),
  });
}

export function useKitchens() {
  return useQuery({
    queryKey: keys.kitchens,
    queryFn: async () => unwrap(await api.GET("/api/v1/management/kitchens")),
    ...poll,
  });
}

export function useOrders(page: number, filters: OrderFilters) {
  return useQuery({
    queryKey: keys.orders(page, filters),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/management/orders", {
          params: { query: { page, ...cleanFilters(filters) } },
        }),
      ),
    placeholderData: keepPreviousData,
    ...poll,
  });
}

export function useOrderDetail(orderId: string) {
  return useQuery({
    queryKey: keys.order(orderId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/management/orders/{order_id}", {
          params: { path: { order_id: orderId } },
        }),
      ),
    ...poll,
  });
}

export function useDeliveries() {
  return useQuery({
    queryKey: keys.deliveries,
    queryFn: async () => unwrap(await api.GET("/api/v1/management/deliveries")),
    ...poll,
  });
}

export function useAgents(enabled = true) {
  return useQuery({
    queryKey: keys.agents,
    queryFn: async () => unwrap(await api.GET("/api/v1/delivery/manage/agents")),
    enabled,
    ...poll,
  });
}

export function useRefunds() {
  return useQuery({
    queryKey: keys.refunds,
    queryFn: async () => unwrap(await api.GET("/api/v1/management/refunds")),
  });
}

export function useInventory(kitchenId: string | undefined) {
  return useQuery({
    queryKey: keys.inventory(kitchenId ?? ""),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/management/kitchens/{kitchen_id}/inventory", {
          params: { path: { kitchen_id: kitchenId ?? "" } },
        }),
      ),
    enabled: Boolean(kitchenId),
  });
}

export function useAudit(page: number, filters: AuditFilters) {
  return useQuery({
    queryKey: keys.audit(page, filters),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/management/audit", {
          params: { query: { page, ...cleanFilters(filters) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useStaff() {
  return useQuery({
    queryKey: keys.staff,
    queryFn: async () => unwrap(await api.GET("/api/v1/management/staff")),
  });
}

// ---------------------------------------------------------------- actions (all need a reason; audited)
function useManagementMutation<V, R>(fn: (vars: V) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    // Refresh every management view at once after an action.
    onSettled: () => client.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useAddStaff() {
  return useManagementMutation(async (body: StaffIn) =>
    unwrap(await api.POST("/api/v1/management/staff", { body })),
  );
}

async function noContent(run: Promise<{ error?: unknown; response: Response }>): Promise<void> {
  const result = await run;
  // 204 has no body; on failure `unwrap` throws the typed ApiError with the backend message.
  if (!result.response.ok) unwrap({ error: result.error, response: result.response });
}

export function useRemoveRole() {
  return useManagementMutation(async ({ assignmentId, reason }: { assignmentId: string; reason: string }) =>
    noContent(
      api.POST("/api/v1/management/staff/roles/{assignment_id}/remove", {
        params: { path: { assignment_id: assignmentId } },
        body: { reason },
      }),
    ),
  );
}

export function useSetStaffStatus() {
  return useManagementMutation(
    async ({ userId, active, reason }: { userId: string; active: boolean; reason: string }) =>
      noContent(
        api.PUT("/api/v1/management/staff/{user_id}/status", {
          params: { path: { user_id: userId } },
          body: { active, reason },
        }),
      ),
  );
}

export function useForceOffline() {
  return useManagementMutation(async ({ agentId, reason }: { agentId: string; reason: string }) =>
    noContent(
      api.POST("/api/v1/delivery/manage/agents/{agent_id}/force-offline", {
        params: { path: { agent_id: agentId } },
        body: { reason },
      }),
    ),
  );
}

export function useAssignAgent() {
  return useManagementMutation(
    async ({ orderId, agentId, reason }: { orderId: string; agentId: string; reason: string }) =>
      unwrap(
        await api.POST("/api/v1/delivery/manage/orders/{order_id}/assign", {
          params: { path: { order_id: orderId } },
          body: { agent_user_id: agentId, reason },
        }),
      ),
  );
}

export function useFailureDecision() {
  return useManagementMutation(
    async ({ orderId, approve, reason }: { orderId: string; approve: boolean; reason: string }) =>
      unwrap(
        await api.POST("/api/v1/delivery/manage/orders/{order_id}/failure-decision", {
          params: { path: { order_id: orderId } },
          body: { approve, reason },
        }),
      ),
  );
}

export function useReissueCode() {
  return useManagementMutation(async ({ orderId, reason }: { orderId: string; reason: string }) =>
    unwrap(
      await api.POST("/api/v1/delivery/manage/orders/{order_id}/code", {
        params: { path: { order_id: orderId } },
        body: { reason },
      }),
    ),
  );
}

export function useCannotFulfil() {
  return useManagementMutation(async ({ orderId, reason }: { orderId: string; reason: string }) =>
    unwrap(
      await api.POST("/api/v1/kitchen/orders/{order_id}/reject", {
        params: { path: { order_id: orderId } },
        body: { reason },
      }),
    ),
  );
}
