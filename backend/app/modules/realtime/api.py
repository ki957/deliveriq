"""`/api/v1/realtime` WebSocket (DDR-115 (5)–(8)). Not part of the OpenAPI contract (REST only).

Handshake: the session cookie authenticates; the Origin must be this app's origin or a configured dev
origin, otherwise the handshake is refused (cross-site WebSocket hijacking; a WS handshake cannot carry
the CSRF header). Frames from the client: `{"type": "subscribe"|"unsubscribe", "topics": [...]}`.
Frames to the client: `{"type": "ready"}`, `{"type": "subscribed"|"denied", "topic": ...}` and hints
`{topic, kind, id}` (nothing else). Close 4401 = signed out or revoked; 1013 = realtime unavailable.
"""

from __future__ import annotations

import asyncio
import contextlib
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.modules.identity.dependencies import SESSION_COOKIE
from app.modules.realtime import domain as d
from app.modules.realtime import service
from app.modules.realtime.hub import CLOSE_REVOKED, CLOSE_UNAVAILABLE, Client, hub

router = APIRouter()
REVALIDATE_SECONDS = 60  # DDR-115 (7): a cap, not a business value; revocation itself is immediate


def origin_allowed(origin: str | None, host: str | None) -> bool:
    if not origin or not host:
        return False
    return urlsplit(origin).netloc == host or origin in get_settings().cors_origin_list


async def _writer(ws: WebSocket, client: Client) -> None:
    while True:
        item = await client.queue.get()
        if isinstance(item, tuple):
            with contextlib.suppress(Exception):
                await ws.close(code=item[1])
            return
        await ws.send_json(item)


async def _handle(client: Client, message: str) -> None:
    parsed = d.client_topics(message)
    if parsed is None:
        client.send({"type": "error", "detail": "Unknown message"})
        return
    action, topics = parsed
    for raw in topics:
        try:
            topic = d.parse_topic(raw, me=client.principal.user_id)
        except d.BadTopic:
            client.send({"type": "denied", "topic": str(raw)[:60]})
            continue
        name, asked = str(topic), str(raw)
        if action == "unsubscribe":
            client.topics.pop(name, None)
            client.names.pop(name, None)
            continue
        if len(client.topics) >= d.MAX_TOPICS and name not in client.topics:
            client.send({"type": "denied", "topic": asked})
            continue
        access = await run_in_threadpool(service.authorize, client.principal, topic)
        if access is None:
            client.topics.pop(name, None)
            client.names.pop(name, None)
            client.send({"type": "denied", "topic": asked})
        else:
            client.topics[name] = access.regions
            client.names[name] = asked
            client.send({"type": "subscribed", "topic": asked})


async def _revalidate(client: Client) -> None:
    while True:
        await asyncio.sleep(REVALIDATE_SECONDS)
        live = await run_in_threadpool(service.principal, client.session_token, touch=False)
        if live is None:
            client.close(CLOSE_REVOKED)
            return


@router.websocket("/api/v1/realtime")
async def realtime(ws: WebSocket) -> None:
    if not origin_allowed(ws.headers.get("origin"), ws.headers.get("host")):
        await ws.close(code=1008)  # before accept: the handshake is refused (HTTP 403)
        return
    await ws.accept()
    token = ws.cookies.get(SESSION_COOKIE)
    principal = await run_in_threadpool(service.principal, token, touch=True) if token else None
    if principal is None:
        await ws.close(code=CLOSE_REVOKED)
        return
    if not hub.ready:
        await ws.close(code=CLOSE_UNAVAILABLE)
        return
    client = Client(principal, token or "")
    hub.register(client)
    client.send({"type": "ready"})
    writer = asyncio.create_task(_writer(ws, client))
    checker = asyncio.create_task(_revalidate(client))
    try:
        while not writer.done():
            receive = asyncio.create_task(ws.receive_text())
            done, _ = await asyncio.wait({receive, writer}, return_when=asyncio.FIRST_COMPLETED)
            if receive not in done:
                receive.cancel()
                break
            await _handle(client, receive.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unregister(client)
        checker.cancel()
        if not writer.done():
            writer.cancel()
        for task in (checker, writer):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
