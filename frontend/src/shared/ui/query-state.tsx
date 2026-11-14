import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ApiError } from "@/shared/api/client";
import { isForbidden, isNotFound } from "@/shared/api/errors";
import { DeniedState, EmptyState, ErrorState, LoadingState } from "./states";

/**
 * The loading, denied, not-found and error states for a query (PL-17). Returns null once data is
 * available, so the caller renders the success view. A 403 from the backend shows the denied state.
 */
export function queryState<T>(
  query: UseQueryResult<T>,
  { loading, notFound }: { loading?: string; notFound?: string } = {},
): ReactNode | null {
  if (query.isPending) return loading ? <LoadingState label={loading} /> : <LoadingState />;
  if (query.isError) {
    if (isForbidden(query.error)) return <DeniedState />;
    if (isNotFound(query.error)) return <EmptyState title={notFound ?? "Not found"} />;
    // 422: the request was refused for a stated reason (e.g. a date range too long); show it.
    if (query.error instanceof ApiError && query.error.status === 422) {
      return <ErrorState title="Check the filters">{query.error.detail}</ErrorState>;
    }
    return <ErrorState>This information could not be loaded. Try again shortly.</ErrorState>;
  }
  return null;
}
