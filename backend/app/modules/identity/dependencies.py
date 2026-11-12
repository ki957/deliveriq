"""Request dependencies shared by every protected route: CSRF check and the current principal."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.permissions import Principal
from app.modules.identity import service

SESSION_COOKIE = "diq_session"
DEVICE_COOKIE = "diq_device"
CSRF_HEADER = "X-DeliverIQ-CSRF"
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_protect(request: Request) -> None:
    """Unsafe methods must carry a custom header, which a cross-site form cannot send (DDR-98)."""
    if request.method in _UNSAFE and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing CSRF header")


def optional_principal(request: Request) -> Principal | None:
    token = request.cookies.get(SESSION_COOKIE)
    return service.principal_for_session(token) if token else None


def require_principal(principal: Annotated[Principal | None, Depends(optional_principal)]) -> Principal:
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


CurrentPrincipal = Annotated[Principal, Depends(require_principal)]
