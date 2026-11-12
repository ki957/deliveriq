import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import { routes } from "@/app/router";
import type { Me } from "@/shared/api/client";

type Handler = (request: Request) => Response | Promise<Response>;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

/** Route fetch calls by "METHOD /path"; unknown calls fail the test loudly. */
export function mockApi(handlers: Record<string, Handler>) {
  const calls: Request[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const request = input instanceof Request ? input : new Request(String(input));
    calls.push(request.clone());
    const key = `${request.method} ${new URL(request.url, "http://localhost").pathname}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`Unexpected API call: ${key}`);
    return handler(request);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls };
}

export function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

export function me(overrides: Partial<Me> = {}): Me {
  return {
    user_id: "00000000-0000-0000-0000-000000000001",
    display_name: "Test User",
    roles: [{ role: "CUSTOMER", region_id: null, kitchen_id: null }],
    permissions: ["customer.orders.read", "customer.profile.read"],
    portals: ["customer"],
    ...overrides,
  };
}
