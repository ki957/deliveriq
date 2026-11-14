import { describe, expect, it, vi } from "vitest";

import { RealtimeConnection } from "./connection";

class FakeSocket {
  readyState = 0;
  sent: Record<string, unknown>[] = [];
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  closed = false;
  send(data: string) {
    this.sent.push(JSON.parse(data) as Record<string, unknown>);
  }
  close() {
    this.closed = true;
  }
  serverSays(frame: object) {
    this.readyState = 1;
    this.onmessage?.({ data: JSON.stringify(frame) } as MessageEvent);
  }
  drop(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }
}

function setup() {
  vi.useFakeTimers();
  const sockets: FakeSocket[] = [];
  const conn = new RealtimeConnection(() => {
    const s = new FakeSocket();
    sockets.push(s);
    return s as unknown as WebSocket;
  });
  return { conn, sockets, last: () => sockets[sockets.length - 1] as FakeSocket };
}

describe("realtime connection (DDR-115 (8))", () => {
  it("subscribes after ready, refetches on confirmation and on every hint", () => {
    const { conn, last } = setup();
    const events: string[] = [];
    conn.subscribe("order:1", (e) => events.push(e.type === "hint" ? `hint:${e.hint.kind}` : e.type));
    expect(conn.getStatus()).toBe("connecting");
    expect(conn.isLive("order:1")).toBe(false);

    last().serverSays({ type: "ready" });
    expect(last().sent).toEqual([{ type: "subscribe", topics: ["order:1"] }]);
    last().serverSays({ type: "subscribed", topic: "order:1" });
    expect(conn.isLive("order:1")).toBe(true);
    last().serverSays({ topic: "order:1", kind: "assignment", id: "1" });
    expect(events).toEqual(["resync", "hint:assignment"]);
  });

  it("a denied topic is never live, so its page keeps polling", () => {
    const { conn, last } = setup();
    conn.subscribe("region:9", () => undefined);
    last().serverSays({ type: "ready" });
    last().serverSays({ type: "denied", topic: "region:9" });
    expect(conn.getStatus()).toBe("live");
    expect(conn.isLive("region:9")).toBe(false);
  });

  it("falls back on a drop, reconnects with backoff and resyncs every topic", () => {
    const { conn, sockets, last } = setup();
    const resyncs: string[] = [];
    conn.subscribe("kitchen:1", (e) => e.type === "resync" && resyncs.push("kitchen"));
    last().serverSays({ type: "ready" });
    last().serverSays({ type: "subscribed", topic: "kitchen:1" });

    last().drop(1013);
    expect(conn.getStatus()).toBe("offline");
    expect(conn.isLive("kitchen:1")).toBe(false);
    vi.advanceTimersByTime(999);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(2);
    last().drop(4401); // signed out: still retried, with a longer wait
    vi.advanceTimersByTime(1_999);
    expect(sockets).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(3);

    last().serverSays({ type: "ready" });
    expect(last().sent).toEqual([{ type: "subscribe", topics: ["kitchen:1"] }]);
    last().serverSays({ type: "subscribed", topic: "kitchen:1" });
    expect(resyncs).toEqual(["kitchen", "kitchen"]);
  });

  it("shares one socket, unsubscribes the last listener and closes when idle", () => {
    const { conn, sockets, last } = setup();
    const offA = conn.subscribe("pipelines", () => undefined);
    const offB = conn.subscribe("pipelines", () => undefined);
    last().serverSays({ type: "ready" });
    expect(sockets).toHaveLength(1);
    offA();
    expect(last().sent).toHaveLength(1);
    offB();
    expect(last().sent.at(-1)).toEqual({ type: "unsubscribe", topics: ["pipelines"] });
    vi.advanceTimersByTime(5_000);
    expect(last().closed).toBe(true);
    expect(conn.getStatus()).toBe("offline");
  });

  it("re-subscribing during the idle wait keeps the socket (navigation between pages)", () => {
    vi.useRealTimers(); // real timer functions: they must not be called as methods of the connection
    const sockets: FakeSocket[] = [];
    const conn = new RealtimeConnection(() => {
      const s = new FakeSocket();
      sockets.push(s);
      return s as unknown as WebSocket;
    });
    const off = conn.subscribe("kitchen:1", () => undefined);
    off(); // the page unmounts: the idle close is scheduled
    expect(() => conn.subscribe("kitchen:2", () => undefined)).not.toThrow(); // the next page cancels it
    expect(sockets).toHaveLength(1);
  });

  it("ignores frames that are not hints", () => {
    const { conn, last } = setup();
    const hints: unknown[] = [];
    conn.subscribe("order:1", (e) => e.type === "hint" && hints.push(e));
    last().serverSays({ type: "ready" });
    last().serverSays({ type: "error", topic: "order:1", kind: "x", id: "1" });
    last().onmessage?.({ data: "not json" } as MessageEvent);
    last().serverSays({ topic: "order:2", kind: "order", id: "2" });
    expect(hints).toEqual([]);
  });
});
