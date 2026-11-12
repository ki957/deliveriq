import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Me } from "@/shared/api/client";

export const ME_QUERY_KEY = ["me"] as const;

/** The signed-in principal, or null when there is no valid session (401). */
export async function fetchMe(): Promise<Me | null> {
  const { data, response } = await api.GET("/api/v1/me");
  if (response.status === 401) return null;
  if (!response.ok || !data) throw new Error(`Could not load your account (${response.status})`);
  return data;
}

export function useMe() {
  return useQuery({ queryKey: ME_QUERY_KEY, queryFn: fetchMe, staleTime: 30_000, retry: false });
}

export function useSetMe() {
  const client = useQueryClient();
  return (me: Me | null) => client.setQueryData(ME_QUERY_KEY, me);
}

export function hasPermission(me: Me | null | undefined, permission: string): boolean {
  return Boolean(me?.permissions.includes(permission));
}
