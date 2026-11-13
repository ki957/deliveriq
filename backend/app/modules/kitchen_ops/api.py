"""Kitchen settings routes: /api/v1/kitchen/settings (KI-12–KI-15; DDR-111 (14))."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.kitchen_ops import service
from app.modules.kitchen_ops.domain import Intake
from app.modules.kitchen_ops.schemas import (
    ConfiguredValueOut,
    IntakeOut,
    KitchenSettingsIn,
    KitchenSettingsOut,
)

router = APIRouter(prefix="/api/v1/kitchen/settings", tags=["kitchen"], dependencies=[Depends(csrf_protect)])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except service.MissingSetting as exc:
        raise HTTPException(status_code=409, detail=f"Kitchen setting {exc} is not configured") from None


def intake_out(intake: Intake) -> IntakeOut:
    return IntakeOut(
        mode=intake.mode,
        capacity=intake.capacity,
        active_orders=intake.active,
        accepting=intake.accepting,
        refusal=intake.refusal,
    )


def _value(row: service.SettingRow) -> ConfiguredValueOut:
    return ConfiguredValueOut(value=int(row.value), is_test_default=row.is_test_default)


def _out(s: service.Settings) -> KitchenSettingsOut:
    return KitchenSettingsOut(
        kitchen_id=s.kitchen.id,
        kitchen_name=s.kitchen.name,
        mode=s.kitchen.mode,  # type: ignore[arg-type]
        normal_capacity=_value(s.normal_capacity),
        busy_capacity=_value(s.busy_capacity),
        acceptance_timeout_minutes=_value(s.acceptance_timeout_minutes)
        if s.acceptance_timeout_minutes
        else None,
        intake=intake_out(s.intake),
        can_change=s.can_change,
    )


@router.get("", response_model=KitchenSettingsOut)
def get_settings(principal: CurrentPrincipal, kitchen_id: uuid.UUID | None = None) -> KitchenSettingsOut:
    """Mode, capacities (labelled when they are DDR-42 test defaults) and current intake."""
    return _out(_call(lambda: service.get_settings(principal, kitchen_id)))


@router.put("", response_model=KitchenSettingsOut)
def update_settings(
    body: KitchenSettingsIn, principal: CurrentPrincipal, kitchen_id: uuid.UUID | None = None
) -> KitchenSettingsOut:
    """Change mode and capacities with a reason (KM own kitchen; RM own region; CA). Audited."""
    return _out(
        _call(
            lambda: service.update_settings(
                principal,
                kitchen_id,
                mode=body.mode,
                normal_capacity=body.normal_capacity,
                busy_capacity=body.busy_capacity,
                reason=body.reason,
            )
        )
    )
