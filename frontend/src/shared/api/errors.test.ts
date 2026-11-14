import { describe, expect, it } from "vitest";

import { ApiError } from "./client";
import { shouldRetry } from "./errors";

describe("query retry policy", () => {
  it("never retries a backend refusal (out of scope, denied, invalid)", () => {
    for (const status of [401, 403, 404, 409, 422]) {
      expect(shouldRetry(0, new ApiError(status, "refused", null))).toBe(false);
    }
  });

  it("retries server and network failures up to three times", () => {
    expect(shouldRetry(0, new ApiError(503, "unavailable", null))).toBe(true);
    expect(shouldRetry(2, new TypeError("network"))).toBe(true);
    expect(shouldRetry(3, new ApiError(500, "error", null))).toBe(false);
  });
});
