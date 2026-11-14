"""`/api/v1/me/notifications`: the signed-in person's own notifications (DDR-115 (10))."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.notifications import service
from app.modules.notifications.schemas import InboxOut, MarkReadIn, NotificationOut

router = APIRouter(
    prefix="/api/v1/me/notifications", tags=["notifications"], dependencies=[Depends(csrf_protect)]
)


@router.get("", response_model=InboxOut)
def inbox(principal: CurrentPrincipal) -> InboxOut:
    """The last 30 days, newest first (at most 100), and the unread count."""
    box = service.inbox(principal)
    return InboxOut(
        rows=[NotificationOut.model_validate(r, from_attributes=True) for r in box.rows],
        unread=box.unread,
        history_days=service.HISTORY_DAYS,
    )


@router.post("/read", status_code=204)
def mark_read(body: MarkReadIn, principal: CurrentPrincipal) -> Response:
    """Mark the given notifications (or all, without ids) read; others' ids are ignored."""
    service.mark_read(principal, body.ids)
    return Response(status_code=204)
