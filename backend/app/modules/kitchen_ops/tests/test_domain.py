"""Modes and capacity rules (#4 §3; KI-12–KI-14; DDR-111 (1)–(3))."""

from __future__ import annotations

import pytest

from app.modules.kitchen_ops.domain import (
    REFUSAL_AT_CAPACITY,
    REFUSAL_PAUSED,
    KitchenMode,
    capacity_error,
    intake,
)

pytestmark = pytest.mark.unit


def test_normal_mode_accepts_below_capacity_and_refuses_at_it() -> None:
    assert intake(KitchenMode.NORMAL, capacity=10, active=9).accepting
    full = intake(KitchenMode.NORMAL, capacity=10, active=10)
    assert (full.capacity, full.refusal) == (10, REFUSAL_AT_CAPACITY)


def test_busy_mode_applies_its_own_capacity() -> None:
    busy = intake(KitchenMode.BUSY, capacity=5, active=5)
    assert (busy.capacity, busy.refusal) == (5, REFUSAL_AT_CAPACITY)
    assert intake(KitchenMode.BUSY, capacity=5, active=4).accepting


def test_paused_accepts_nothing_new_even_when_empty() -> None:
    paused = intake(KitchenMode.PAUSED, capacity=None, active=0)
    assert (paused.capacity, paused.refusal, paused.accepting) == (None, REFUSAL_PAUSED, False)


@pytest.mark.parametrize(
    ("normal", "busy", "ok"),
    [(10, 5, True), (10, 10, True), (5, 6, False), (0, 0, False), (51, 5, False), (10, 0, False)],
)
def test_capacity_rules(normal: int, busy: int, ok: bool) -> None:
    assert (capacity_error(normal, busy) is None) is ok
