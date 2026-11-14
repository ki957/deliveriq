import { ApiError } from "./client";

/** User-facing text for an API failure. Backend refusals (409) carry their own rule message. */
export function actionError(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Try again.";
  switch (error.status) {
    case 401:
      return "Your session has ended. Sign in again.";
    case 403:
      return "You don't have permission for this action.";
    case 404:
      return "This item no longer exists or is outside your scope.";
    case 409:
    case 422:
      return error.detail;
    default:
      return "Something went wrong. Try again.";
  }
}

/**
 * React Query retry policy: 401/403/404/409/422 are final answers from the backend (scope, permission,
 * validation), so they are shown at once; other failures are retried up to 3 times.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 3;
}

export function isForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403;
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
