"""Test-only routes, mounted only when APP_ENV is local or test (never in production, DDR-99).

- `GET /api/v1/_test/scope-check` runs the real scope guard for the logged-in principal, so the
  negative matrix (cross-customer, -kitchen, -region, KS→KM, RM→CA) is proven before the business
  endpoints exist. Business endpoints reuse the same `can()` guard (Tasks 6–10).
- `POST /api/v1/_test/reset-otp-limits` clears OTP rate-limit keys so integration tests are
  repeatable.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.permissions import Permission, can
from app.core.redis_client import get_redis
from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect

router = APIRouter(prefix="/api/v1/_test", tags=["test-only"], dependencies=[Depends(csrf_protect)])


@router.get("/scope-check")
def scope_check(
    principal: CurrentPrincipal,
    permission: Permission,
    customer_id: uuid.UUID | None = None,
    kitchen_id: uuid.UUID | None = None,
    region_id: uuid.UUID | None = None,
) -> dict[str, bool]:
    if not can(principal, permission, customer_id=customer_id, kitchen_id=kitchen_id, region_id=region_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"allowed": True}


@router.post("/reset-otp-limits", status_code=204)
def reset_otp_limits() -> None:
    redis = get_redis()
    keys = list(redis.scan_iter(match="otp:*", count=500))
    if keys:
        redis.delete(*keys)
