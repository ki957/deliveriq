"""Pseudonymous customer keys for analytics events (DDR-116 (5); plan Task 12 "pseudonymous customer keys").

`customer_key` = HMAC-SHA256(secret `PSEUDONYM_KEY`, customer id). Stable for one customer, so analytics can
count repeat customers, but not reversible without the secret (a plain hash of a UUID could be matched by
anyone holding the ids). The real customer id never enters `raw` or `analytics`. The key is never rotated in
the POC: a new key would split every customer's history.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

from app.core.config import get_settings


def customer_key(customer_id: uuid.UUID) -> str:
    secret = get_settings().pseudonym_key.get_secret_value().encode()
    return hmac.new(secret, f"customer:{customer_id}".encode(), hashlib.sha256).hexdigest()
