"""Pure realtime rules (DDR-115 (4), (5))."""

from __future__ import annotations

import json
import uuid

import pytest

from app.modules.realtime import domain as d

ME = uuid.uuid4()
ORD, C, K, R, A = (uuid.uuid4() for _ in range(5))


def notice(**fields: object) -> d.Notice:
    payload = d.parse_notice(
        json.dumps({k: str(v) if isinstance(v, uuid.UUID) else v for k, v in fields.items()})
    )
    assert payload is not None
    return payload


def topics(n: d.Notice) -> set[str]:
    return {str(h.topic) for h in d.hints(n)}


def test_topics_parse_strictly_and_agent_me_is_always_the_caller() -> None:
    assert d.parse_topic(f"order:{ORD}", me=ME) == d.Topic("order", ORD)
    assert d.parse_topic("agent:me", me=ME) == d.Topic("agent", ME)
    assert str(d.parse_topic("pipelines", me=ME)) == "pipelines"
    assert d.parse_topic("me", me=ME) == d.Topic("user", ME)
    for bad in (
        f"agent:{A}",
        "order:not-a-uuid",
        "orders",
        "",
        7,
        None,
        "x" * 61,
        f"customer:{C}",
        f"user:{C}",
    ):
        with pytest.raises(d.BadTopic):
            d.parse_topic(bad, me=ME)


def test_an_order_change_reaches_its_customer_kitchen_and_region() -> None:
    n = notice(k="order", id=ORD, o=ORD, c=C, ki=K, r=R, st="ACCEPTED")
    assert topics(n) == {f"order:{ORD}", f"kitchen:{K}", f"region:{R}"}


def test_the_agent_holding_an_order_hears_its_status_changes() -> None:
    n = notice(k="order", id=ORD, o=ORD, c=C, ki=K, r=R, a=A, st="READY_FOR_PICKUP")
    assert f"agent:{A}" in topics(n)


def test_the_kitchen_never_hears_of_an_unpaid_order() -> None:
    n = notice(k="order", id=ORD, o=ORD, c=C, ki=K, r=R, st="PLACED")
    assert topics(n) == {f"order:{ORD}", f"region:{R}"}


def test_assignment_changes_reach_the_agent_and_gps_points_do_not_reach_the_kitchen() -> None:
    assignment = notice(k="assignment", id=ORD, o=ORD, c=C, ki=K, r=R, a=A, st="PREPARING")
    assert topics(assignment) == {f"order:{ORD}", f"kitchen:{K}", f"agent:{A}", f"region:{R}"}
    location = notice(k="location", id=ORD, o=ORD, c=C, ki=K, r=R, a=A, st="OUT_FOR_DELIVERY")
    assert topics(location) == {f"order:{ORD}", f"region:{R}"}


def test_kitchen_agent_and_pipeline_notices() -> None:
    assert topics(notice(k="stock", id=K, ki=K, r=R)) == {f"kitchen:{K}", f"region:{R}"}
    assert topics(notice(k="agent", id=A, a=A, r=R)) == {f"agent:{A}", f"region:{R}"}
    [run] = d.hints(notice(k="run", id=ORD, r=R))
    assert (str(run.topic), run.region) == ("pipelines", R)


def test_a_notification_reaches_only_its_owner() -> None:
    [hint] = d.hints(notice(k="notification", id=ORD, u=C))
    assert (str(hint.topic), hint.kind) == (f"user:{C}", "notification")


def test_hint_frames_carry_only_topic_kind_and_id() -> None:
    n = notice(k="order", id=ORD, o=ORD, c=C, ki=K, r=R, st="ACCEPTED")
    for h in d.hints(n):
        assert set(h.frame()) == {"topic", "kind", "id"}
        assert str(C) not in json.dumps(h.frame())  # the customer id never leaves the server


def test_control_and_malformed_notices_produce_no_hints() -> None:
    assert d.hints(notice(k="session", s=ORD, u=C)) == []
    assert d.hints(notice(k="user", u=C)) == []
    for raw in ("not json", "[]", '{"id": "x"}'):
        assert d.parse_notice(raw) is None


def test_client_frames_are_validated() -> None:
    assert d.client_topics('{"type": "subscribe", "topics": ["pipelines"]}') == ("subscribe", ["pipelines"])
    too_many = json.dumps({"type": "subscribe", "topics": ["pipelines"] * (d.MAX_TOPICS + 1)})
    for bad in ("{", '{"type": "publish", "topics": []}', '{"type": "subscribe", "topics": "x"}', too_many):
        assert d.client_topics(bad) is None
