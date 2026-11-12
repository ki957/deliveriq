import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./generated/schema";

// Typed client generated from the backend OpenAPI schema (DDR-81); never hand-written types.
export const CSRF_HEADER = "X-DeliverIQ-CSRF";

const csrf: Middleware = {
  onRequest({ request }) {
    request.headers.set(CSRF_HEADER, "1");
    return request;
  },
};

export const api = createClient<paths>({
  // Same origin as the page; Vite proxies /api to the backend.
  baseUrl: globalThis.location?.origin ?? "",
  credentials: "same-origin",
  // Resolved per call, so tests can replace globalThis.fetch.
  fetch: (request) => globalThis.fetch(request),
});
api.use(csrf);

export type Me = components["schemas"]["MeOut"];
export type Portal = components["schemas"]["Portal"];
export const PORTALS: readonly Portal[] = ["customer", "kitchen", "delivery", "management"];

export function isPortal(value: string | undefined): value is Portal {
  return PORTALS.includes(value as Portal);
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly retryAfter: number | null,
  ) {
    super(detail);
  }
}

/** Turn an openapi-fetch result into data or a typed ApiError (the backend error envelope). */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined && result.response.ok) return result.data;
  const body = (result.error ?? {}) as { message?: string; detail?: string };
  const retry = result.response.headers.get("Retry-After");
  throw new ApiError(
    result.response.status,
    body.message ?? body.detail ?? "Request failed",
    retry ? Number(retry) : null,
  );
}
