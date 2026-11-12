import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

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
    return <ErrorState>This information could not be loaded. Try again shortly.</ErrorState>;
  }
  return null;
}
