"""Deterministic local/test proposal adapter for the Operational Actions harness.

The mock accepts only explicit, fully identified requests. It never executes a tool.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

_ID = r"([0-9a-fA-F-]{36})"
_REASON = r"\s+Reason:\s*(.{1,500})\s*"


@dataclass(frozen=True)
class Proposal:
    action: str
    arguments: dict[str, str | int | bool]
    summary: str


def _id(value: str) -> str:
    return str(uuid.UUID(value))


def propose(request: str) -> Proposal | None:
    text = request.strip()
    rules = (
        (
            (
                rf"Set kitchen {_ID} to (NORMAL|BUSY|PAUSED) with normal capacity (\d+) "
                rf"and busy capacity (\d+)\.{_REASON}"
            ),
            "kitchen_settings",
        ),
        (rf"Assign order {_ID} to agent {_ID}\.{_REASON}", "agent_assign"),
        (rf"(Approve|Reject) dish availability request {_ID}\.{_REASON}", "dish_availability"),
        (rf"Publish TEST menu item {_ID}\.{_REASON}", "menu_publish"),
    )
    for pattern, action in rules:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        parts = match.groups()
        if action == "kitchen_settings":
            kitchen_id, mode, normal, busy, reason = parts
            arguments: dict[str, str | int | bool] = {
                "kitchen_id": _id(kitchen_id),
                "mode": mode.upper(),
                "normal_capacity": int(normal),
                "busy_capacity": int(busy),
                "reason": reason.strip(),
            }
        elif action == "agent_assign":
            order_id, agent_id, reason = parts
            arguments = {"order_id": _id(order_id), "agent_id": _id(agent_id), "reason": reason.strip()}
        elif action == "dish_availability":
            decision, request_id, reason = parts
            arguments = {
                "request_id": _id(request_id),
                "approve": decision.lower() == "approve",
                "reason": reason.strip(),
            }
        else:
            item_id, reason = parts
            arguments = {"item_id": _id(item_id), "reason": reason.strip()}
        return Proposal(action, arguments, text.partition(". Reason:")[0])
    return None
