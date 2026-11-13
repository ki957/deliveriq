"""Read operational values from `app.config_settings` (migrations 0005, 0009). Kitchen, then region,
then global scope; a missing key is an error, never a silent default."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Connection, text


class MissingConfig(LookupError):
    pass


def value(
    conn: Connection, key: str, *, kitchen_id: uuid.UUID | None = None, region_id: uuid.UUID | None = None
) -> Decimal:
    row = conn.execute(
        text(
            "SELECT value FROM app.config_settings WHERE key = :k AND ("
            "(scope_type = 'KITCHEN' AND kitchen_id = :kit) OR (scope_type = 'REGION' AND region_id = :reg) "
            "OR scope_type = 'GLOBAL') "
            "ORDER BY CASE scope_type WHEN 'KITCHEN' THEN 1 WHEN 'REGION' THEN 2 ELSE 3 END LIMIT 1"
        ),
        {"k": key, "kit": kitchen_id, "reg": region_id},
    ).scalar_one_or_none()
    if row is None:
        raise MissingConfig(key)
    return Decimal(row)
