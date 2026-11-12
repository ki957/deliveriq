"""Order fulfilment and item preparation state machines (Matrix §7.1–7.2, DDR-16, DDR-17).

Pure domain code: standard library only. The same transitions are enforced in PostgreSQL
(migration 0003); a test asserts both definitions are identical.
"""

from __future__ import annotations

from enum import StrEnum


class Fulfilment(StrEnum):
    PLACED = "PLACED"
    PENDING_KITCHEN = "PENDING_KITCHEN"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    PICKED_UP = "PICKED_UP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    DELIVERY_FAILED = "DELIVERY_FAILED"


class ItemPrep(StrEnum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"


F = Fulfilment
FULFILMENT_INITIAL = frozenset({F.PLACED})
FULFILMENT_TRANSITIONS = frozenset(
    {
        (F.PLACED, F.PENDING_KITCHEN),
        (F.PLACED, F.CANCELLED),
        (F.PENDING_KITCHEN, F.ACCEPTED),
        (F.PENDING_KITCHEN, F.REJECTED),
        (F.PENDING_KITCHEN, F.CANCELLED),
        (F.ACCEPTED, F.PREPARING),
        (F.PREPARING, F.READY_FOR_PICKUP),
        (F.READY_FOR_PICKUP, F.PICKED_UP),
        (F.PICKED_UP, F.OUT_FOR_DELIVERY),
        (F.OUT_FOR_DELIVERY, F.DELIVERED),
        (F.OUT_FOR_DELIVERY, F.DELIVERY_FAILED),
    }
)
FULFILMENT_TERMINAL = frozenset({F.DELIVERED, F.CANCELLED, F.REJECTED, F.DELIVERY_FAILED})

ITEM_INITIAL = frozenset({ItemPrep.PENDING})
ITEM_TRANSITIONS = frozenset(
    {(ItemPrep.PENDING, ItemPrep.PREPARING), (ItemPrep.PREPARING, ItemPrep.PREPARED)}
)


def can_fulfil(current: Fulfilment, target: Fulfilment) -> bool:
    return (current, target) in FULFILMENT_TRANSITIONS


def can_prepare(current: ItemPrep, target: ItemPrep) -> bool:
    return (current, target) in ITEM_TRANSITIONS
