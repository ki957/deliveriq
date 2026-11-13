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

export function isForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403;
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
