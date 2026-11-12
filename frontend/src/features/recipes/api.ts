import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

type S = components["schemas"];
export type RecipeVersion = S["RecipeVersionOut"];
export type RecipeDetail = S["RecipeVersionDetailOut"];
export type ReviewItem = S["ReviewItemOut"];
export type RecipeStatus = S["RecipeStatus"];
export type SignoffType = S["SignoffType"];
export type Action = S["TransitionIn"]["action"];

export const keys = {
  versions: ["recipes", "versions"] as const,
  version: (id: string) => ["recipes", "version", id] as const,
  review: (status: string) => ["recipes", "review", status] as const,
};

// Mirrors the backend workflow (DDR-10, DDR-107) so the UI offers only steps that apply; the backend
// and the database decide (KM-only activation, five sign-offs, open review items, no SOP activation).
export const ACTIONS: { action: Action; from: RecipeStatus; label: string; confirm: string }[] = [
  { action: "submit", from: "DRAFT", label: "Submit for validation", confirm: "Confirm submit" },
  { action: "return", from: "PENDING_VALIDATION", label: "Return to draft", confirm: "Confirm return" },
  { action: "validate", from: "PENDING_VALIDATION", label: "Mark validated", confirm: "Confirm validate" },
  { action: "reject", from: "VALIDATED", label: "Reject", confirm: "Confirm reject" },
  { action: "activate", from: "VALIDATED", label: "Activate", confirm: "Confirm activate" },
];
export const KM_SIGNOFFS: SignoffType[] = ["CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER"];
export const SIGNOFF_STATUSES: RecipeStatus[] = ["PENDING_VALIDATION", "VALIDATED"];
export const SIGNOFF_LABELS: Record<SignoffType, string> = {
  CHEF: "Chef",
  FOOD_SAFETY_LEAD: "Food-safety lead",
  INVENTORY_OWNER: "Inventory owner",
  KITCHEN_MANAGER: "Kitchen Manager",
  PRODUCT_OWNER: "Product owner",
};

export function useVersions() {
  return useQuery({
    queryKey: keys.versions,
    queryFn: async () => unwrap(await api.GET("/api/v1/recipes/versions")),
  });
}

export function useVersion(id: string) {
  return useQuery({
    queryKey: keys.version(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/recipes/versions/{version_id}", { params: { path: { version_id: id } } }),
      ),
  });
}

export function useReviewItems(status: "OPEN" | "ACKNOWLEDGED" | "ALL") {
  return useQuery({
    queryKey: keys.review(status),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/recipes/review-items", {
          params: { query: status === "ALL" ? { limit: 500 } : { status, limit: 500 } },
        }),
      ),
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ["recipes"] });
}

export function useTransition(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ action, reason }: { action: Action; reason: string }) =>
      unwrap(
        await api.POST("/api/v1/recipes/versions/{version_id}/transitions", {
          params: { path: { version_id: id } },
          body: { action, reason },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useSignoff(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ type, note }: { type: SignoffType; note: string }) => {
      const result = await api.POST("/api/v1/recipes/versions/{version_id}/signoffs", {
        params: { path: { version_id: id } },
        body: { signoff_type: type, note },
      });
      // 204 has no body, so only failures go through unwrap (which keeps the backend's message).
      if (!result.response.ok) unwrap(result);
    },
    onSuccess: refresh,
  });
}

export function useAcknowledge() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, note }: { id: string; note: string }) =>
      unwrap(
        await api.POST("/api/v1/recipes/review-items/{item_id}/acknowledge", {
          params: { path: { item_id: id } },
          body: { note },
        }),
      ),
    onSuccess: refresh,
  });
}
