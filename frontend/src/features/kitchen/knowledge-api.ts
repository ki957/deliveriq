import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";

export const knowledgeKeys = {
  versions: ["kitchen-knowledge", "versions"] as const,
  goldenSet: ["kitchen-knowledge", "golden-set"] as const,
};

export function useKitchenKnowledgeVersions(enabled: boolean) {
  return useQuery({
    queryKey: knowledgeKeys.versions,
    queryFn: async () => unwrap(await api.GET("/api/v1/knowledge/kitchen/versions")),
    enabled,
  });
}

export function useKitchenGoldenSet(enabled: boolean) {
  return useQuery({
    queryKey: knowledgeKeys.goldenSet,
    queryFn: async () => unwrap(await api.GET("/api/v1/knowledge/kitchen/golden-set")),
    enabled,
  });
}

export function useDecideKitchenKnowledge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      versionId,
      approve,
      reason,
    }: {
      versionId: string;
      approve: boolean;
      reason: string;
    }) =>
      unwrap(
        await api.POST(
          approve
            ? "/api/v1/knowledge/kitchen/versions/{version_id}/approve"
            : "/api/v1/knowledge/kitchen/versions/{version_id}/reject",
          { params: { path: { version_id: versionId } }, body: { reason } },
        ),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: knowledgeKeys.versions });
    },
  });
}

export function useApproveKitchenGoldenSet() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ setId, reason }: { setId: string; reason: string }) =>
      unwrap(
        await api.POST("/api/v1/knowledge/kitchen/golden-set/{set_id}/approve", {
          params: { path: { set_id: setId } },
          body: { reason },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: knowledgeKeys.goldenSet });
    },
  });
}
