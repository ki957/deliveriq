"""P2 landing over the real stack (plan Task 12; DATA_PIPELINE §13; DDR-116 (5), (6), (10), (13)).

Needs the core stack, fixtures and the worker (its landing thread moves outbox rows to raw). `raw.events` is
append-only, so the rejected TEST event this module writes stays there, flagged as a fixture.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest

from app.modules.identity.tests.test_auth_integration import World
from app.modules.management.tests.test_management_integration import Team, prepaid_order
from app.pipelines.p2_elt.landing import land_batch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

BACKLOG = "/api/v1/pipelines/p2/backlog"


def wait_for(check: Callable[[], Any], timeout: float = 15.0) -> Any:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.25)
    raise AssertionError("timed out waiting for the landing thread (is `make worker` running?)")


def raw_rows(world: World, event_id: object) -> list[tuple[Any, ...]]:
    return world.db.execute(
        "SELECT event_type, parse_status, parse_error, data, is_test_fixture FROM raw.events WHERE event_id = %s",
        (event_id,),
    ).fetchall()


def outbox_event(world: World, order_id: str, event_type: str) -> tuple[Any, ...]:
    row = world.db.execute(
        "SELECT event_id, published_at FROM app.outbox WHERE aggregate_id = %s AND event_type = %s",
        (order_id, event_type),
    ).fetchone()
    assert row is not None
    return tuple(row)


@pytest.fixture
def p2_elt() -> Iterator[Any]:
    from sqlalchemy import create_engine

    url = (
        f"postgresql+psycopg://p2_elt:{os.environ['P2_ELT_PASSWORD']}@127.0.0.1:"
        f"{os.environ.get('INTEGRATION_DB_PORT', '5433')}/{os.environ['POSTGRES_DB']}"
    )
    engine = create_engine(url)
    yield engine
    engine.dispose()


def test_events_land_once_with_a_pseudonymous_key_and_never_the_customer_id(world: World, team: Team) -> None:
    order_id = prepaid_order(world, team)
    event_id, _ = outbox_event(world, order_id, "order.placed")
    wait_for(lambda: outbox_event(world, order_id, "order.placed")[1])
    [(event_type, status, error, data, fixture)] = raw_rows(world, event_id)
    assert (event_type, status, error, fixture) == ("order.placed", "accepted", None, True)
    owner = world.db.execute("SELECT customer_user_id FROM app.orders WHERE id = %s", (order_id,)).fetchone()
    assert owner is not None
    secret = os.environ["PSEUDONYM_KEY"].encode()
    expected = hmac.new(secret, f"customer:{owner[0]}".encode(), hashlib.sha256).hexdigest()
    assert data["customer_key"] == expected
    assert str(owner[0]) not in json.dumps(data)


def test_replay_lands_nothing_twice(world: World, team: Team) -> None:
    order_id = prepaid_order(world, team)
    wait_for(lambda: outbox_event(world, order_id, "order.placed")[1])
    event_id, _ = outbox_event(world, order_id, "order.placed")
    world.db.execute("UPDATE app.outbox SET published_at = NULL WHERE event_id = %s", (event_id,))  # replay
    wait_for(lambda: outbox_event(world, order_id, "order.placed")[1])
    assert len(raw_rows(world, event_id)) == 1


def test_a_malformed_event_lands_rejected_with_its_reason(world: World) -> None:
    event_id, aggregate = uuid.uuid4(), uuid.uuid4()
    world.db.execute(
        "INSERT INTO app.outbox (event_id, event_type, event_version, occurred_at, aggregate_type, aggregate_id, "
        "idempotency_key, data, is_test_fixture) VALUES (%s, 'delivery.location', 1, now(), 'order', %s, %s, "
        "'{}'::jsonb, true)",
        (event_id, aggregate, f"test:{event_id}"),
    )
    [(event_type, status, error, _data, fixture)] = wait_for(lambda: raw_rows(world, event_id))
    assert (event_type, status, fixture) == ("delivery.location", "rejected", True)
    assert error == "unknown event type 'delivery.location'"
    # No location events are ever accepted into raw (DDR-78).
    accepted = world.db.execute(
        "SELECT count(*) FROM raw.events WHERE event_type LIKE '%%location%%' AND parse_status = 'accepted'"
    ).fetchone()
    assert accepted is not None and accepted[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # append-only: kept, never deleted
        world.db.execute("DELETE FROM raw.events WHERE event_id = %s", (event_id,))


def test_an_interrupted_batch_lands_nothing_and_loses_nothing(world: World, team: Team, p2_elt: Any) -> None:
    for _ in range(5):  # the worker may land the row first; then try again with a new order
        order_id = prepaid_order(world, team)
        event_id, _ = outbox_event(world, order_id, "order.placed")
        with p2_elt.connect() as conn:
            conn.begin()
            landed = land_batch(conn)
            claimed = conn.exec_driver_sql(
                "SELECT count(*) FROM raw.events WHERE event_id = %(e)s", {"e": event_id}
            ).scalar_one()
            conn.rollback()  # the worker "dies" before commit
        if landed.accepted and claimed:
            break
    else:
        pytest.skip("the landing thread always won the race")
    assert raw_rows(world, event_id) == [] or outbox_event(world, order_id, "order.placed")[1] is not None
    # Nothing was lost: the worker lands it afterwards, exactly once.
    wait_for(lambda: outbox_event(world, order_id, "order.placed")[1])
    assert len(raw_rows(world, event_id)) == 1


def test_only_a_global_viewer_sees_the_backlog(team: Team) -> None:
    body = team.ca.get(BACKLOG).json()
    assert set(body) == {
        "waiting", "oldest_waiting_at", "oldest_age_seconds", "landed", "rejected", "warn_after_seconds",
        "warn_is_test_default",
    }  # fmt: skip
    assert body["warn_after_seconds"] == 300 and body["warn_is_test_default"] is True
    assert body["landed"] >= 1
    assert team.rm.get(BACKLOG).status_code == 403
    assert team.customer.get(BACKLOG).status_code == 403
