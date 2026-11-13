"""SQL for kitchen mode and capacity settings. Parameterised; callers own the transaction.

The active-order count reads `app.orders` (read only); the orders module owns every order write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Connection, text

KEY_NORMAL = "MAX_CONCURRENT_ORDERS"
KEY_BUSY = "MAX_CONCURRENT_ORDERS_BUSY"
KEY_TIMEOUT = "KITCHEN_ACCEPTANCE_TIMEOUT"


@dataclass(frozen=True)
class KitchenRow:
    id: uuid.UUID
    region_id: uuid.UUID
    name: str
    mode: str


@dataclass(frozen=True)
class SettingRow:
    value: Decimal
    is_test_default: bool


def find(conn: Connection, kitchen_id: uuid.UUID, *, lock: bool = False) -> KitchenRow | None:
    sql = "SELECT id, region_id, name, mode FROM app.kitchens WHERE id = :id"
    row = conn.execute(text(sql + (" FOR UPDATE" if lock else "")), {"id": kitchen_id}).first()
    return KitchenRow(*row) if row else None


def active_count(conn: Connection, kitchen_id: uuid.UUID) -> int:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM app.orders WHERE kitchen_id = :k "
            "AND fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP')"
        ),
        {"k": kitchen_id},
    ).scalar_one()
    return count


def setting(conn: Connection, key: str, kitchen: KitchenRow) -> SettingRow | None:
    """Kitchen, then region, then global value of a key, with its test-default label."""
    row = conn.execute(
        text(
            "SELECT value, is_test_default FROM app.config_settings WHERE key = :key AND ("
            "(scope_type = 'KITCHEN' AND kitchen_id = :k) OR (scope_type = 'REGION' AND region_id = :r) "
            "OR scope_type = 'GLOBAL') "
            "ORDER BY CASE scope_type WHEN 'KITCHEN' THEN 1 WHEN 'REGION' THEN 2 ELSE 3 END LIMIT 1"
        ),
        {"key": key, "k": kitchen.id, "r": kitchen.region_id},
    ).first()
    return SettingRow(Decimal(row[0]), bool(row[1])) if row else None


def set_mode(conn: Connection, kitchen_id: uuid.UUID, mode: str) -> None:
    conn.execute(text("UPDATE app.kitchens SET mode = :m WHERE id = :id"), {"m": mode, "id": kitchen_id})


def set_kitchen_value(conn: Connection, key: str, kitchen_id: uuid.UUID, value: int, unit: str) -> None:
    """A value set in kitchen settings is a configured value, no longer a labelled test default."""
    updated = conn.execute(
        text(
            "UPDATE app.config_settings SET value = :v, is_test_default = false, "
            "source_ref = 'Kitchen settings (DDR-111 (14))' "
            "WHERE key = :key AND scope_type = 'KITCHEN' AND kitchen_id = :k"
        ),
        {"v": value, "key": key, "k": kitchen_id},
    ).rowcount
    if not updated:
        conn.execute(
            text(
                "INSERT INTO app.config_settings (key, value, unit, scope_type, kitchen_id, is_test_default, "
                "source_ref) VALUES (:key, :v, :u, 'KITCHEN', :k, false, 'Kitchen settings (DDR-111 (14))')"
            ),
            {"key": key, "v": value, "u": unit, "k": kitchen_id},
        )
