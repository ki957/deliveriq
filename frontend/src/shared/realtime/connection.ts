// Realtime hints (DDR-115 (4)–(8); PL-14). One socket per tab, shared by every page. The server sends
// `{topic, kind, id}` hints only; listeners refetch their REST view. While the socket is down, pages keep
// polling (the fallback), and every (re)subscription triggers a full refetch of that topic's views.

export type Status = "connecting" | "live" | "offline";
export type Hint = { topic: string; kind: string; id: string };
type Listener = (event: { type: "hint"; hint: Hint } | { type: "resync" }) => void;

const BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000];
const IDLE_CLOSE_MS = 5_000; // close the socket a little after the last page unsubscribes

type Socket = Pick<WebSocket, "send" | "close" | "readyState"> & {
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
};

export class RealtimeConnection {
  private socket: Socket | null = null;
  private status: Status = "offline";
  private readonly topics = new Map<string, Set<Listener>>();
  // Topics the server confirmed; a page is "live" only for these.
  private readonly confirmed = new Set<string>();
  private readonly statusListeners = new Set<() => void>();
  private attempt = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;

  // Wrapped, never stored bare: browsers throw "Illegal invocation" when timer functions are called as
  // methods of another object (`this.cancel(id)`).
  private readonly schedule = (fn: () => void, ms: number) => setTimeout(fn, ms);
  private readonly cancel = (id: ReturnType<typeof setTimeout>) => clearTimeout(id);

  constructor(private readonly open: () => Socket) {}

  // ---------------------------------------------------------------- status (useSyncExternalStore)
  getStatus = (): Status => this.status;

  isLive(topic: string): boolean {
    return this.status === "live" && this.confirmed.has(topic);
  }

  onStatus = (listener: () => void): (() => void) => {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  };

  private setStatus(status: Status): void {
    this.status = status;
    for (const l of this.statusListeners) l();
  }

  // ---------------------------------------------------------------- subscriptions
  subscribe(topic: string, listener: Listener): () => void {
    let listeners = this.topics.get(topic);
    if (!listeners) {
      listeners = new Set();
      this.topics.set(topic, listeners);
      this.send({ type: "subscribe", topics: [topic] });
    }
    listeners.add(listener);
    if (this.idleTimer) {
      this.cancel(this.idleTimer);
      this.idleTimer = null;
    }
    this.ensureOpen();
    return () => {
      const set = this.topics.get(topic);
      if (!set) return;
      set.delete(listener);
      if (set.size === 0) {
        this.topics.delete(topic);
        this.confirmed.delete(topic);
        this.send({ type: "unsubscribe", topics: [topic] });
        this.setStatus(this.status);
      }
      if (this.topics.size === 0) this.idleTimer = this.schedule(() => this.shutdown(), IDLE_CLOSE_MS);
    };
  }

  private send(frame: object): void {
    if (this.socket && this.socket.readyState === 1 && this.status === "live") {
      this.socket.send(JSON.stringify(frame));
    }
  }

  private ensureOpen(): void {
    if (this.socket || this.retryTimer) return;
    this.setStatus("connecting");
    let socket: Socket;
    try {
      socket = this.open();
    } catch {
      this.retry();
      return;
    }
    this.socket = socket;
    socket.onmessage = (ev) => this.receive(String(ev.data));
    socket.onclose = () => {
      this.socket = null;
      this.confirmed.clear();
      this.setStatus("offline");
      if (this.topics.size > 0) this.retry();
    };
  }

  private receive(data: string): void {
    let frame: Record<string, unknown>;
    try {
      frame = JSON.parse(data) as Record<string, unknown>;
    } catch {
      return;
    }
    if (frame.type === "ready") {
      this.attempt = 0;
      this.setStatus("live");
      if (this.topics.size > 0) this.send({ type: "subscribe", topics: [...this.topics.keys()] });
      return;
    }
    const topic = typeof frame.topic === "string" ? frame.topic : null;
    if (!topic) return;
    if (frame.type === "subscribed") {
      this.confirmed.add(topic);
      this.setStatus("live");
      // Reconnect (or first subscribe) refetches the canonical REST state (PL-14).
      for (const l of this.topics.get(topic) ?? []) l({ type: "resync" });
      return;
    }
    if (frame.type === "denied") {
      this.confirmed.delete(topic);
      this.setStatus(this.status);
      return;
    }
    if (typeof frame.kind === "string" && typeof frame.id === "string" && frame.type === undefined) {
      const hint: Hint = { topic, kind: frame.kind, id: frame.id };
      for (const l of this.topics.get(topic) ?? []) l({ type: "hint", hint });
    }
  }

  private retry(): void {
    const delay = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)] ?? 30_000;
    this.attempt += 1;
    this.retryTimer = this.schedule(() => {
      this.retryTimer = null;
      if (this.topics.size > 0) this.ensureOpen();
    }, delay);
  }

  private shutdown(): void {
    this.idleTimer = null;
    if (this.topics.size > 0) return;
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onclose = null;
      socket.close();
    }
    this.confirmed.clear();
    this.setStatus("offline");
  }
}

function openBrowserSocket(): Socket {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${scheme}://${location.host}/api/v1/realtime`);
}

export const realtime = new RealtimeConnection(openBrowserSocket);
