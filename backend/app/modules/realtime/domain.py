"""Pure realtime rules (DDR-115 (4), (5)): topics, notices → hints, client frames. No I/O.

A notice comes from the `app.rt_notify()` trigger (migration 0012) with ids and scope only. A hint is
what a socket receives: exactly `{topic, kind, id}`. The client refetches its REST view, so labels,
PII rules and scope stay exactly as REST has them.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

# Order kinds that also concern the kitchen and the agent; locations go to the customer and managers only.
ORDER_KINDS = frozenset({"order", "assignment", "location"})
KITCHEN_KINDS = frozenset({"kitchen", "stock", "availability"})
CONTROL_KINDS = frozenset({"session", "user"})
# Before payment the kitchen never sees an order (Matrix §7.3: PLACED has no kitchen label).
HIDDEN_FROM_KITCHEN = frozenset({"PLACED"})
MAX_TOPICS = 50


@dataclass(frozen=True)
class Topic:
    """`order:<id>`, `kitchen:<id>`, `region:<id>`, `agent:<user id>`, `user:<user id>` or `pipelines`."""

    kind: str
    ref: uuid.UUID | None = None

    def __str__(self) -> str:
        return self.kind if self.ref is None else f"{self.kind}:{self.ref}"


SCOPED_TOPICS = frozenset({"order", "kitchen", "region", "agent", "user"})


class BadTopic(ValueError):
    pass


def parse_topic(raw: object, *, me: uuid.UUID) -> Topic:
    """Client topic names; `agent:me` and `me` are always the caller's own (never another person's)."""
    if not isinstance(raw, str) or len(raw) > 60:
        raise BadTopic(str(raw)[:60])
    if raw == "pipelines":
        return Topic("pipelines")
    if raw == "agent:me":
        return Topic("agent", me)
    if raw == "me":
        return Topic("user", me)  # the caller's notifications (DDR-115 (10))
    kind, _, ref = raw.partition(":")
    if kind not in SCOPED_TOPICS - {"agent", "user"}:
        raise BadTopic(raw)
    try:
        return Topic(kind, uuid.UUID(ref))
    except ValueError:
        raise BadTopic(raw) from None


@dataclass(frozen=True)
class Notice:
    kind: str
    id: uuid.UUID | None
    order: uuid.UUID | None
    kitchen: uuid.UUID | None
    region: uuid.UUID | None
    agent: uuid.UUID | None
    status: str | None
    session: uuid.UUID | None
    user: uuid.UUID | None


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def parse_notice(payload: str) -> Notice | None:
    """None for anything malformed: a bad notice is dropped, never guessed."""
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("k"), str):
        return None
    return Notice(
        kind=data["k"],
        id=_uuid(data.get("id")),
        order=_uuid(data.get("o")),
        kitchen=_uuid(data.get("ki")),
        region=_uuid(data.get("r")),
        agent=_uuid(data.get("a")),
        status=data.get("st") if isinstance(data.get("st"), str) else None,
        session=_uuid(data.get("s")),
        user=_uuid(data.get("u")),
    )


@dataclass(frozen=True)
class Hint:
    topic: Topic
    kind: str
    id: uuid.UUID
    # Pipelines only: the run's region, filtered per subscriber (RM own-region runs, DDR-105).
    region: uuid.UUID | None = None

    def frame(self) -> dict[str, str]:
        return {"topic": str(self.topic), "kind": self.kind, "id": str(self.id)}


def hints(n: Notice) -> list[Hint]:
    """Which topics a notice concerns. Control notices (session, user) produce no hints."""
    if n.kind in CONTROL_KINDS or n.id is None:
        return []
    if n.kind == "notification":
        return [Hint(Topic("user", n.user), n.kind, n.id)] if n.user is not None else []
    out: list[Hint] = []
    if n.kind in ORDER_KINDS and n.order is not None:
        out.append(Hint(Topic("order", n.order), n.kind, n.id))
        if n.kitchen is not None and n.kind != "location" and n.status not in HIDDEN_FROM_KITCHEN:
            out.append(Hint(Topic("kitchen", n.kitchen), n.kind, n.id))
        # The agent holding the order hears order, item and assignment changes (e.g. Ready → pickup).
        if n.agent is not None and n.kind != "location":
            out.append(Hint(Topic("agent", n.agent), n.kind, n.id))
    elif n.kind in KITCHEN_KINDS and n.kitchen is not None:
        out.append(Hint(Topic("kitchen", n.kitchen), n.kind, n.id))
    elif n.kind == "agent" and n.agent is not None:
        out.append(Hint(Topic("agent", n.agent), n.kind, n.id))
    elif n.kind == "run":
        out.append(Hint(Topic("pipelines"), n.kind, n.id, region=n.region))
        return out
    if n.region is not None and n.kind in ORDER_KINDS | KITCHEN_KINDS | {"agent"}:
        out.append(Hint(Topic("region", n.region), n.kind, n.id))
    return out


def client_topics(message: str) -> tuple[str, list[object]] | None:
    """`{"type": "subscribe"|"unsubscribe", "topics": [...]}` → (type, topics); None if malformed."""
    try:
        data = json.loads(message)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("type") not in ("subscribe", "unsubscribe"):
        return None
    topics = data.get("topics")
    if not isinstance(topics, list) or len(topics) > MAX_TOPICS:
        return None
    return data["type"], topics
