"""Management AI platform routes (DDR-119)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.modules.ai import service
from app.modules.ai.actions import service as actions
from app.modules.ai.schemas import (
    ActionConfirmIn,
    ActionProposalOut,
    ActionRequestIn,
    ActionResultOut,
    AiModelOut,
    AiSettingsIn,
    AiSettingsOut,
    AiStatusOut,
    CopilotIn,
    CopilotOut,
)
from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect

router = APIRouter(
    prefix="/api/v1/management/ai", tags=["management-ai"], dependencies=[Depends(csrf_protect)]
)


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/status", response_model=AiStatusOut)
def ai_status(principal: CurrentPrincipal) -> AiStatusOut:
    s = _call(lambda: service.status(principal))
    return AiStatusOut(
        enabled=s.enabled,
        knowledge_status=s.knowledge_status,
        models=[AiModelOut(logical_name=n, capabilities=c, selected=x) for n, c, x in s.models],
        conversation_turn_limit=6,
        request_metadata_retention_days=90,
    )


@router.get("/settings", response_model=AiSettingsOut)
def ai_settings(principal: CurrentPrincipal) -> AiSettingsOut:
    model, updated = _call(lambda: service.settings(principal))
    return AiSettingsOut(harness="management_copilot", logical_model=model, updated_at=updated)


@router.put("/settings", response_model=AiSettingsOut)
def update_ai_settings(body: AiSettingsIn, principal: CurrentPrincipal) -> AiSettingsOut:
    model, updated = _call(lambda: service.set_settings(principal, body.logical_model, body.reason))
    return AiSettingsOut(harness="management_copilot", logical_model=model, updated_at=updated)


@router.post("/copilot", response_model=CopilotOut)
def ask_copilot(body: CopilotIn, principal: CurrentPrincipal) -> CopilotOut:
    answer, conversation_id, model = _call(
        lambda: service.copilot(principal, body.question, body.conversation_id)
    )
    return CopilotOut(
        answer=answer,
        conversation_id=conversation_id,
        logical_model=model,
        simulated=True,
        knowledge_status="pending approval",
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, principal: CurrentPrincipal) -> None:
    _call(lambda: service.delete_conversation(principal, conversation_id))


def _action_call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except actions.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except actions.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except actions.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except actions.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/actions/proposals", response_model=ActionProposalOut)
def propose_action(body: ActionRequestIn, principal: CurrentPrincipal) -> ActionProposalOut:
    return ActionProposalOut.model_validate(_action_call(lambda: actions.propose(principal, body.request)))


@router.post("/actions/proposals/{proposal_id}/confirm", response_model=ActionResultOut)
def confirm_action(
    proposal_id: uuid.UUID, body: ActionConfirmIn, principal: CurrentPrincipal
) -> ActionResultOut:
    return ActionResultOut(
        result=_action_call(lambda: actions.confirm(principal, proposal_id, body.idempotency_key))
    )
