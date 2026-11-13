import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

type S = components["schemas"];
export type History = S["HistoryOut"];
export type PointIn = S["PointIn"];

// Poll while the tab is visible until realtime (Task 11); the offer countdown needs a fresh view.
export const POLL_MS = 5_000;
const keys = { me: ["delivery", "me"] as const, history: ["delivery", "history"] as const };

/** A refusal with the backend's message (409 wrong step, 422 reason or code problems). */
export class DeliveryRefusal extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(run: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const result = await run;
  if (result.response.ok) return result.data as T;
  const body = (result.error ?? {}) as { message?: string; detail?: string };
  throw new DeliveryRefusal(result.response.status, body.message ?? body.detail ?? "Request failed");
}

export function refusalText(error: unknown): string {
  if (typeof navigator !== "undefined" && !navigator.onLine)
    return "You are offline. Reconnect and try again.";
  if (!(error instanceof DeliveryRefusal)) return "Something went wrong. Try again.";
  if (error.status === 403) return "You don't have permission for this action.";
  if (error.status === 404) return "This delivery is no longer yours (it may have been reassigned).";
  return error.message;
}

export type MyWork = NonNullable<ReturnType<typeof useMyWork>["data"]>;
export type WorkOrder = NonNullable<MyWork["order"]>;

export function useMyWork() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => unwrap(await api.GET("/api/v1/delivery/me")),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });
}

function useAction<A, T>(run: (arg: A) => Promise<T>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSettled: () => client.invalidateQueries({ queryKey: ["delivery"] }),
  });
}

export function useSetAvailability() {
  return useAction((online: boolean) =>
    call(api.PUT("/api/v1/delivery/me/availability", { body: { online } })),
  );
}

export function useRespond() {
  return useAction(({ id, accept, reason }: { id: string; accept: boolean; reason?: string }) =>
    call(
      api.POST("/api/v1/delivery/assignments/{assignment_id}/respond", {
        params: { path: { assignment_id: id } },
        body: { accept, reason: reason ?? null },
      }),
    ),
  );
}

type OrderPath = { params: { path: { order_id: string } } };
const path = (id: string): OrderPath => ({ params: { path: { order_id: id } } });

export function usePickup() {
  return useAction((id: string) => call(api.POST("/api/v1/delivery/orders/{order_id}/pickup", path(id))));
}

export function useDeliver() {
  return useAction(({ id, code }: { id: string; code: string }) =>
    call(api.POST("/api/v1/delivery/orders/{order_id}/deliver", { ...path(id), body: { code } })),
  );
}

export function useCod() {
  return useAction(({ id, collected, reason }: { id: string; collected: boolean; reason?: string }) =>
    call(
      api.POST("/api/v1/delivery/orders/{order_id}/cod", {
        ...path(id),
        body: { collected, reason: reason ?? null },
      }),
    ),
  );
}

export function useCustomerUnavailable() {
  return useAction((id: string) =>
    call(api.POST("/api/v1/delivery/orders/{order_id}/customer-unavailable", path(id))),
  );
}

export function useContactManager() {
  return useAction(({ id, reason }: { id: string; reason?: string }) =>
    call(
      api.POST("/api/v1/delivery/orders/{order_id}/contact-manager", {
        ...path(id),
        body: { reason: reason ?? null },
      }),
    ),
  );
}

export function useFailureRequest() {
  return useAction(({ id, refused, reason }: { id: string; refused: boolean; reason: string }) =>
    call(
      api.POST("/api/v1/delivery/orders/{order_id}/failure-request", {
        ...path(id),
        body: { refused, reason },
      }),
    ),
  );
}

export async function revealPhone(id: string): Promise<string> {
  const result = await call(api.GET("/api/v1/delivery/orders/{order_id}/customer-phone", path(id)));
  return result.phone;
}

export async function sendPoints(points: PointIn[]): Promise<S["IngestOut"]> {
  return call(api.POST("/api/v1/delivery/locations", { body: { points } }));
}

export function useHistory() {
  return useQuery({
    queryKey: keys.history,
    queryFn: async () => unwrap(await api.GET("/api/v1/delivery/history")),
  });
}

export function useRename() {
  return useAction((display_name: string) =>
    call(api.PUT("/api/v1/delivery/me/name", { body: { display_name } })),
  );
}
