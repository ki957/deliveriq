import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";

type S = components["schemas"];
export type MenuItem = S["ManagedMenuItemOut"];
export type MenuAction = S["MenuTransitionIn"]["action"];
export type RecipeVersion = S["RecipeVersionOut"];
export type RecipeDetail = S["RecipeVersionDetailOut"];

const keys = {
  menu: ["approvals", "menu"] as const,
  signoff: ["approvals", "signoff"] as const,
  version: (id: string) => ["approvals", "version", id] as const,
};

// Steps an RM (own region) or CA can take now (DDR-31, DDR-107). The database checks readiness.
export const MENU_ACTIONS: { action: MenuAction; from: MenuItem["publication_status"]; label: string }[] = [
  { action: "mark_ready", from: "DRAFT", label: "Mark ready for publication" },
  { action: "publish", from: "READY_FOR_PUBLICATION", label: "Publish" },
];

export function useManagedMenu() {
  return useQuery({
    queryKey: keys.menu,
    queryFn: async () => unwrap(await api.GET("/api/v1/menu/manage/items")),
  });
}

export function useMenuTransition() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: MenuAction }) =>
      unwrap(
        await api.POST("/api/v1/menu/manage/items/{item_id}/transitions", {
          params: { path: { item_id: id } },
          body: { action },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.menu });
    },
  });
}

/** TEST recipes awaiting validation sign-offs; the CA's read scope is TEST recipes only (DDR-106). */
export function useSignoffQueue() {
  return useQuery({
    queryKey: keys.signoff,
    queryFn: async () => {
      const all = unwrap(await api.GET("/api/v1/recipes/versions"));
      return all.filter(
        (v) => v.is_test_fixture && (v.status === "PENDING_VALIDATION" || v.status === "VALIDATED"),
      );
    },
  });
}

export function useSignoffDetail(id: string) {
  return useQuery({
    queryKey: keys.version(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/recipes/versions/{version_id}", { params: { path: { version_id: id } } }),
      ),
  });
}

export function useProductOwnerSignoff(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (note: string) => {
      const result = await api.POST("/api/v1/recipes/versions/{version_id}/signoffs", {
        params: { path: { version_id: id } },
        body: { signoff_type: "PRODUCT_OWNER", note },
      });
      if (!result.response.ok) unwrap(result);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
}
