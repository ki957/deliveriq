import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";

export const customerKnowledgeKeys = {
  versions: ["customer-knowledge", "versions"] as const,
  goldenSet: ["customer-knowledge", "golden-set"] as const,
};

export function useCustomerKnowledgeVersions(enabled: boolean) {
  return useQuery({
    queryKey: customerKnowledgeKeys.versions,
    queryFn: async () => unwrap(await api.GET("/api/v1/knowledge/customer/versions")),
    enabled,
  });
}

export function useCustomerGoldenSet(enabled: boolean) {
  return useQuery({
    queryKey: customerKnowledgeKeys.goldenSet,
    queryFn: async () => unwrap(await api.GET("/api/v1/knowledge/customer/golden-set")),
    enabled,
  });
}

export function useDecideCustomerKnowledge() {
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
            ? "/api/v1/knowledge/customer/versions/{version_id}/approve"
            : "/api/v1/knowledge/customer/versions/{version_id}/reject",
          { params: { path: { version_id: versionId } }, body: { reason } },
        ),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: customerKnowledgeKeys.versions }),
  });
}

export function useApproveCustomerGoldenSet() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ setId, reason }: { setId: string; reason: string }) =>
      unwrap(
        await api.POST("/api/v1/knowledge/customer/golden-set/{set_id}/approve", {
          params: { path: { set_id: setId } },
          body: { reason },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: customerKnowledgeKeys.goldenSet }),
  });
}
