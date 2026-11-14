import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";
import { useLiveRefresh } from "@/shared/realtime/use-live";

export type Inbox = components["schemas"]["InboxOut"];
export type Notification = components["schemas"]["NotificationOut"];

const keys = { inbox: ["notifications"] as const };
// While live updates are down, check for new notifications every 30 s (the page itself is not urgent).
const FALLBACK_MS = 30_000;

/** The signed-in person's own notifications; new ones arrive live on the `me` topic (DDR-115 (10)). */
export function useInbox(enabled = true) {
  const live = useLiveRefresh(enabled ? ["me"] : [], [keys.inbox]);
  return useQuery({
    queryKey: keys.inbox,
    queryFn: async () => unwrap(await api.GET("/api/v1/me/notifications")),
    enabled,
    refetchInterval: live ? false : FALLBACK_MS,
    refetchIntervalInBackground: false,
  });
}

export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (ids: string[] | null) => {
      const result = await api.POST("/api/v1/me/notifications/read", { body: { ids } });
      if (!result.response.ok) unwrap({ error: result.error, response: result.response });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.inbox });
    },
  });
}

const short = (id: string | null) => (id ? id.slice(0, 8) : "");

/** Wording per kind (CU-25, DL-16, KI-23); the API carries ids and kinds only. */
export function describe(n: Notification): { text: string; to: string } {
  const o = short(n.order_id);
  const order = `/customer/orders/${n.order_id ?? ""}`;
  switch (n.kind) {
    case "order.accepted":
      return { text: `The kitchen accepted your order ${o}.`, to: order };
    case "order.preparing":
      return { text: `Your order ${o} is being prepared.`, to: order };
    case "order.ready_for_pickup":
      return { text: `Your order ${o} is ready for the delivery agent.`, to: order };
    case "order.out_for_delivery":
      return { text: `Your order ${o} is out for delivery.`, to: order };
    case "order.delivered":
      return { text: `Your order ${o} was delivered.`, to: order };
    case "order.cancelled":
      return { text: `Your order ${o} was cancelled.`, to: order };
    case "order.rejected":
      return { text: `The kitchen could not take your order ${o}.`, to: order };
    case "order.delivery_failed":
      return { text: `The delivery of your order ${o} failed.`, to: order };
    case "order.agent_assigned":
      return { text: `A delivery agent is assigned to your order ${o}.`, to: order };
    case "delivery.offered":
      return { text: `New delivery offer: order ${o}.`, to: "/delivery" };
    case "delivery.withdrawn":
      return { text: `Order ${o} was withdrawn from you (reassigned or cancelled).`, to: "/delivery" };
    case "delivery.failure_returned":
      return {
        text: `Your failure request for order ${o} was returned: continue the delivery.`,
        to: "/delivery",
      };
    case "delivery.failure_approved":
      return { text: `Your failure request for order ${o} was approved.`, to: "/delivery/history" };
    case "stock.low":
      return { text: `Low stock: ${n.ingredient_name ?? "an ingredient"}.`, to: "/kitchen/inventory" };
  }
}
