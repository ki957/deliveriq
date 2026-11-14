"""Realtime relay and socket hub (DDR-115 (2), (3), (7), (8); PL-14). Async by design (DDR-82).

relay:      Postgres LISTEN `deliveriq_rt` → Redis PUBLISH `deliveriq:rt` (raw notice text).
subscriber: Redis SUBSCRIBE → parse → hints for subscribed sockets; control notices close sockets.

If either side is down the hub is not ready: open sockets are closed (1013) and new ones are refused,
so every page falls back to REST polling (DOCKER §8: "Realtime falls back to REST polling").
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import psycopg
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.permissions import Principal
from app.modules.realtime import domain as d

log = logging.getLogger(__name__)

PG_CHANNEL = "deliveriq_rt"
REDIS_CHANNEL = "deliveriq:rt"
QUEUE_MAX = 200  # a socket this far behind is closed; the client reconnects and refetches
RETRY_SECONDS = (1, 2, 5, 10, 30)
CLOSE_REVOKED = 4401
CLOSE_UNAVAILABLE = 1013


@dataclass(eq=False)
class Client:
    principal: Principal
    session_token: str
    queue: asyncio.Queue[dict[str, Any] | tuple[str, int]] = field(
        default_factory=lambda: asyncio.Queue(QUEUE_MAX)
    )
    topics: dict[str, frozenset[uuid.UUID] | None] = field(default_factory=dict)
    # Canonical topic → the name the client used (`agent:me`), so frames match the client's request.
    names: dict[str, str] = field(default_factory=dict)

    def send(self, frame: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(frame)
        except asyncio.QueueFull:
            self.close(CLOSE_UNAVAILABLE)

    def close(self, code: int) -> None:
        # The writer stops at the first close; a full queue is cleared so the close always fits.
        while self.queue.full():
            self.queue.get_nowait()
        self.queue.put_nowait(("close", code))


class Hub:
    def __init__(self) -> None:
        self.clients: set[Client] = set()
        self._relay_up = False
        self._subscriber_up = False
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def ready(self) -> bool:
        return self._relay_up and self._subscriber_up

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._relay()), asyncio.create_task(self._subscribe())]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._close_all(CLOSE_UNAVAILABLE)

    def register(self, client: Client) -> None:
        self.clients.add(client)

    def unregister(self, client: Client) -> None:
        self.clients.discard(client)

    def _close_all(self, code: int) -> None:
        for client in list(self.clients):
            client.close(code)

    # ---------------------------------------------------------------- dispatch
    def dispatch(self, payload: str) -> None:
        notice = d.parse_notice(payload)
        if notice is None:
            return
        if notice.kind == "session" and notice.session is not None:
            for c in list(self.clients):
                if c.principal.session_id == notice.session:
                    c.close(CLOSE_REVOKED)
            return
        if notice.kind == "user" and notice.user is not None:
            for c in list(self.clients):
                if c.principal.user_id == notice.user:
                    c.close(CLOSE_REVOKED)
            return
        for hint in d.hints(notice):
            topic = str(hint.topic)
            for c in self.clients:
                if topic not in c.topics:
                    continue
                regions = c.topics[topic]
                if hint.topic.kind == "pipelines" and regions is not None and hint.region not in regions:
                    continue  # an RM sees own-region runs only (DDR-105); region-less hints are CA-only
                frame = hint.frame()
                frame["topic"] = c.names.get(topic, topic)
                c.send(frame)

    # ---------------------------------------------------------------- background loops
    async def _relay(self) -> None:
        settings = get_settings()
        conninfo = settings.database_url.set(drivername="postgresql").render_as_string(hide_password=False)
        redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_connect_timeout=2)
        attempt = 0
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
                    await conn.execute(f"LISTEN {PG_CHANNEL}")
                    self._relay_up, attempt = True, 0
                    async for note in conn.notifies():
                        await redis.publish(REDIS_CHANNEL, note.payload)
            except asyncio.CancelledError:
                raise
            except Exception:  # any outage: fall back to polling and retry
                log.warning("realtime relay down; retrying", exc_info=True)
            self._relay_up = False
            self._close_all(CLOSE_UNAVAILABLE)
            await asyncio.sleep(RETRY_SECONDS[min(attempt, len(RETRY_SECONDS) - 1)])
            attempt += 1

    async def _subscribe(self) -> None:
        url = get_settings().redis_url.get_secret_value()
        attempt = 0
        while True:
            try:
                redis = Redis.from_url(url, socket_connect_timeout=2)
                async with redis.pubsub() as pubsub:
                    await pubsub.subscribe(REDIS_CHANNEL)
                    self._subscriber_up, attempt = True, 0
                    async for message in pubsub.listen():
                        if message.get("type") == "message":
                            data = message["data"]
                            self.dispatch(data.decode() if isinstance(data, bytes) else str(data))
            except asyncio.CancelledError:
                raise
            except Exception:  # Redis down: fall back to polling and retry
                log.warning("realtime subscriber down; retrying", exc_info=True)
            self._subscriber_up = False
            self._close_all(CLOSE_UNAVAILABLE)
            await asyncio.sleep(RETRY_SECONDS[min(attempt, len(RETRY_SECONDS) - 1)])
            attempt += 1


hub = Hub()
