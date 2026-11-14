import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/shared/api/client";
import type { components } from "@/shared/api/generated/schema";
import { useLiveRefresh } from "@/shared/realtime/use-live";
import { ACTIVE_RUN_STATUSES } from "@/shared/ui/status-tones";

export type Pipeline = components["schemas"]["PipelineOut"];
export type Run = components["schemas"]["RunSummaryOut"];
export type RunDetail = components["schemas"]["RunDetailOut"];
export type Backlog = components["schemas"]["BacklogOut"];
export type P2Status = components["schemas"]["P2StatusOut"];

// Live stage hints (DDR-115 (13)); REST polling every 2 s while a run is active and hints are down (DDR-105).
export const POLL_MS = 2000;

export function isActive(run: Pick<Run, "status"> | null | undefined): boolean {
  return Boolean(run && ACTIVE_RUN_STATUSES.has(run.status));
}

export function pollInterval(active: boolean): number | false {
  return active ? POLL_MS : false;
}

export const keys = {
  pipelines: ["pipelines"] as const,
  runs: (pipeline: string) => ["pipelines", "runs", pipeline] as const,
  run: (id: string) => ["pipelines", "run", id] as const,
  backlog: ["pipelines", "backlog"] as const,
  p2: ["pipelines", "p2-status"] as const,
};

function usePipelinesLive(): boolean {
  return useLiveRefresh(["pipelines"], [keys.pipelines]);
}

export function usePipelines() {
  const live = usePipelinesLive();
  return useQuery({
    queryKey: keys.pipelines,
    queryFn: async () => unwrap(await api.GET("/api/v1/pipelines")),
    refetchInterval: (q) => !live && pollInterval(Boolean(q.state.data?.some((p) => isActive(p.last_run)))),
  });
}

/** P2 outbox backlog (DATA_PIPELINE §12; DDR-116 (10)): CA only; live hints, else every 10 s. */
export function useBacklog(enabled: boolean) {
  const live = usePipelinesLive();
  return useQuery({
    queryKey: keys.backlog,
    queryFn: async () => unwrap(await api.GET("/api/v1/pipelines/p2/backlog")),
    enabled,
    refetchInterval: live ? false : 10_000,
    refetchIntervalInBackground: false,
  });
}

/** P2 freshness and schedule (DDR-116 (8)–(10)): every pipeline viewer, RM included. */
export function useP2Status(enabled: boolean) {
  const live = usePipelinesLive();
  return useQuery({
    queryKey: keys.p2,
    queryFn: async () => unwrap(await api.GET("/api/v1/pipelines/p2/status")),
    enabled,
    refetchInterval: live ? false : 10_000,
    refetchIntervalInBackground: false,
  });
}

export function useSetP2Schedule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { enabled: boolean; interval_minutes: number; reason: string }) =>
      unwrap(await api.PUT("/api/v1/pipelines/p2/schedule", { body })),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.pipelines });
    },
  });
}

export function useRuns(pipeline: string) {
  const live = usePipelinesLive();
  return useQuery({
    queryKey: keys.runs(pipeline),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/pipelines/runs", { params: { query: { pipeline, limit: 50 } } })),
    refetchInterval: (q) => !live && pollInterval(Boolean(q.state.data?.some(isActive))),
  });
}

export function useRunDetail(runId: string) {
  const live = usePipelinesLive();
  return useQuery({
    queryKey: keys.run(runId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/pipelines/runs/{run_id}", { params: { path: { run_id: runId } } })),
    refetchInterval: (q) => !live && pollInterval(isActive(q.state.data?.run)),
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: keys.pipelines });
  };
}

export function useTriggerRun() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ pipeline, inputRef }: { pipeline: string; inputRef: string }) =>
      unwrap(
        await api.POST("/api/v1/pipelines/runs", {
          body: { pipeline, input_ref: inputRef as "sop" | "fault:records" | "fault:structural" },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useCancelRun(runId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/pipelines/runs/{run_id}/cancel", { params: { path: { run_id: runId } } }),
      ),
    onSuccess: invalidate,
  });
}

export function useRetryRun(runId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/pipelines/runs/{run_id}/retry", { params: { path: { run_id: runId } } }),
      ),
    onSuccess: invalidate,
  });
}

/** Same-origin GET with the session cookie; the browser downloads the Markdown report. */
export function reportHref(runId: string): string {
  return `/api/v1/pipelines/runs/${encodeURIComponent(runId)}/report`;
}

// Pipelines without code yet are shown honestly with the task that builds them (DDR-100;
// plan Tasks 12 P2, 14 P3, 15 Management knowledge, 16 Kitchen RAG, 17 Customer RAG).
export const PLANNED_TASK: Record<string, number> = {
  p3_synthetic: 14,
  k1_customer: 17,
  k2_kitchen: 16,
  k3_management: 15,
};

export function inputLabel(ref: string | null | undefined): string {
  switch (ref) {
    case "sop":
    case null:
    case undefined:
      return "Kitchen SOP (committed copy)";
    case "fault:records":
      return "TEST – fault file: record faults";
    case "fault:structural":
      return "TEST – fault file: broken structure";
    case "run":
      return "Build analytics from landed events";
    case "fault:reconciliation":
      return "TEST – fault: reconciliation mismatch";
    default:
      return ref;
  }
}
