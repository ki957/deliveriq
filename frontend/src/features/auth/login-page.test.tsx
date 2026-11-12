import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { json, me, mockApi, renderAt } from "@/test/render";

import { messageFor, safeNext } from "./login-page";
import { ApiError } from "@/shared/api/client";

const trustedFails = { "POST /api/v1/auth/trusted-login": () => json({ detail: "x" }, 401) };

describe("login page", () => {
  it("signs a returning customer in with a code and lands on the portal", async () => {
    const { calls } = mockApi({
      ...trustedFails,
      "POST /api/v1/auth/otp/request": () => json({ status: "sent_if_eligible" }, 202),
      "POST /api/v1/auth/otp/verify": () => json(me()),
      "GET /api/v1/me": () => json(me()),
    });
    const router = renderAt("/customer/login");
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Mobile number"), "98765 43210");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await user.type(await screen.findByLabelText("6-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/customer"));
    const verify = calls.find((c) => c.url.endsWith("/otp/verify"));
    expect(verify?.headers.get("X-DeliverIQ-CSRF")).toBe("1");
    expect(await verify?.json()).toMatchObject({ portal: "customer", code: "123456", trust_device: false });
  });

  it("asks a new customer for a name and resubmits the same code", async () => {
    let verifyCalls = 0;
    const { calls } = mockApi({
      ...trustedFails,
      "POST /api/v1/auth/otp/request": () => json({ status: "sent_if_eligible" }, 202),
      "POST /api/v1/auth/otp/verify": () =>
        ++verifyCalls === 1 ? json({ code: "http_422", message: "name_required" }, 422) : json(me()),
      "GET /api/v1/me": () => json(me()),
    });
    renderAt("/customer/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Mobile number"), "9876543210");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await user.type(await screen.findByLabelText("6-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await user.type(await screen.findByLabelText("Your name"), "Asha");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(verifyCalls).toBe(2));
    const second = calls.filter((c) => c.url.endsWith("/otp/verify"))[1];
    expect(await second?.json()).toMatchObject({ code: "123456", display_name: "Asha" });
  });

  it("shows the retry time when rate-limited", async () => {
    mockApi({
      ...trustedFails,
      "POST /api/v1/auth/otp/request": () => json({ message: "slow" }, 429, { "Retry-After": "27" }),
    });
    renderAt("/kitchen/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Mobile number"), "9876543210");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 27 seconds");
  });

  it("uses a trusted device without asking for a code", async () => {
    mockApi({
      "POST /api/v1/auth/trusted-login": () => json(me()),
      "GET /api/v1/me": () => json(me()),
    });
    const router = renderAt("/customer/login");
    await waitFor(() => expect(router.state.location.pathname).toBe("/customer"));
  });

  it("redirects an unknown portal to the start page", async () => {
    const router = renderAt("/admin/login");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});

describe("login helpers", () => {
  it("accepts only same-portal redirect targets", () => {
    expect(safeNext("kitchen", "/kitchen/recipes")).toBe("/kitchen/recipes");
    expect(safeNext("kitchen", "/management")).toBe("/kitchen");
    expect(safeNext("kitchen", "https://evil.example")).toBe("/kitchen");
    expect(safeNext("kitchen", "//evil.example")).toBe("/kitchen");
    expect(safeNext("kitchen", null)).toBe("/kitchen");
  });

  it("maps every backend error to a non-revealing message", () => {
    expect(messageFor(new ApiError(400, "", null))).toMatch(/invalid or has expired/);
    expect(messageFor(new ApiError(503, "", null))).toMatch(/temporarily unavailable/);
    expect(messageFor(new Error("x"))).toMatch(/Something went wrong/);
  });
});
