import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// No server in unit tests: the realtime socket never opens, so pages use their polling fallback.
// Realtime behaviour is tested against `RealtimeConnection` with a fake socket (realtime.test.ts).
class ClosedSocket {
  readyState = 0;
  onopen = null;
  onmessage = null;
  onclose = null;
  send(): void {}
  close(): void {}
}

beforeEach(() => vi.stubGlobal("WebSocket", ClosedSocket));
afterEach(() => cleanup());
