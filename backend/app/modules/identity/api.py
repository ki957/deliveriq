"""Identity routes: /api/v1/auth/* (login, logout) and /api/v1/me (principal, devices)."""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings
from app.core.permissions import Principal
from app.core.redis_client import get_redis
from app.modules.identity import domain as d
from app.modules.identity import service
from app.modules.identity.dependencies import (
    DEVICE_COOKIE,
    SESSION_COOKIE,
    CurrentPrincipal,
    csrf_protect,
)
from app.modules.identity.otp_delivery import OtpUnavailable, sender_for
from app.modules.identity.rate_limit import OtpLimiter, RateLimited, RedisLike
from app.modules.identity.schemas import (
    DeviceOut,
    GrantOut,
    MeOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    TrustedLoginIn,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(csrf_protect)])
me_router = APIRouter(prefix="/api/v1/me", tags=["me"], dependencies=[Depends(csrf_protect)])

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _limiter() -> OtpLimiter:
    # redis-py's overloaded signatures are wider than the small protocol the limiter needs.
    return OtpLimiter(cast(RedisLike, get_redis()))


LimiterDep = Annotated[OtpLimiter, Depends(_limiter)]


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def _otp_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Login is temporarily unavailable")


def _set_cookie(response: Response, settings: Settings, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def _me(principal: Principal) -> MeOut:
    return MeOut(
        user_id=principal.user_id,
        display_name=service.display_name(principal.user_id),
        roles=[
            GrantOut(role=g.role, region_id=g.region_id, kitchen_id=g.kitchen_id) for g in principal.grants
        ],
        permissions=sorted(p.value for p in principal.permissions()),
        portals=principal.portals(),
    )


def _login_response(issued: service.IssuedLogin, settings: Settings) -> JSONResponse:
    response = JSONResponse(_me(issued.principal).model_dump(mode="json"))
    _set_cookie(response, settings, SESSION_COOKIE, issued.session_token, d.SESSION_ABSOLUTE_SECONDS)
    if issued.device_token is not None:
        _set_cookie(response, settings, DEVICE_COOKIE, issued.device_token, d.TRUSTED_DEVICE_SECONDS)
    return response


# ---------------------------------------------------------------- auth
@auth_router.post("/otp/request", status_code=202, response_model=OtpRequestOut)
def request_otp(
    body: OtpRequestIn, request: Request, settings: SettingsDep, limiter: LimiterDep
) -> OtpRequestOut:
    ip = request.client.host if request.client else "unknown"
    try:
        service.request_otp(settings, limiter, sender_for(settings), body.mobile, body.portal, ip)
    except service.InvalidMobile:
        raise HTTPException(status_code=422, detail="Enter a valid Indian mobile number") from None
    except RateLimited as limited:
        raise _too_many(limited.retry_after) from None
    except (OtpUnavailable, RedisError):
        # No SMS channel or no Redis: fail closed (DDR-96, DDR-98).
        raise _otp_unavailable() from None
    return OtpRequestOut()


@auth_router.post("/otp/verify", response_model=MeOut)
def verify_otp(body: OtpVerifyIn, settings: SettingsDep, limiter: LimiterDep) -> JSONResponse:
    try:
        issued = service.verify_otp(
            settings,
            limiter,
            body.mobile,
            body.portal,
            body.code,
            display_name=body.display_name,
            trust_device=body.trust_device,
            device_label=body.device_label,
        )
    except service.InvalidMobile:
        raise HTTPException(status_code=422, detail="Enter a valid Indian mobile number") from None
    except service.InvalidCode:
        raise HTTPException(status_code=400, detail="The code is invalid or has expired") from None
    except service.NameRequired:
        raise HTTPException(status_code=422, detail="name_required") from None
    except RateLimited as limited:
        raise _too_many(limited.retry_after) from None
    except RedisError:
        raise _otp_unavailable() from None
    return _login_response(issued, settings)


@auth_router.post("/trusted-login", response_model=MeOut)
def trusted_login(body: TrustedLoginIn, request: Request, settings: SettingsDep) -> JSONResponse:
    token = request.cookies.get(DEVICE_COOKIE)
    try:
        if token is None:
            raise service.TrustedLoginFailed
        issued = service.trusted_login(token, body.portal)
    except service.TrustedLoginFailed:
        response = JSONResponse({"detail": "Sign in with a one-time code"}, status_code=401)
        response.delete_cookie(DEVICE_COOKIE, path="/")
        return response
    return _login_response(issued, settings)


@auth_router.post("/logout", status_code=204)
def logout(principal: CurrentPrincipal) -> Response:
    service.logout(principal)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


# ---------------------------------------------------------------- me
@me_router.get("", response_model=MeOut)
def me(principal: CurrentPrincipal) -> MeOut:
    return _me(principal)


@me_router.get("/devices", response_model=list[DeviceOut])
def my_devices(principal: CurrentPrincipal) -> list[DeviceOut]:
    return [
        DeviceOut(id=dev.id, label=dev.label, created_at=dev.created_at, expires_at=dev.expires_at)
        for dev in service.list_devices(principal)
    ]


@me_router.delete("/devices/{device_id}", status_code=204)
def revoke_my_device(device_id: uuid.UUID, principal: CurrentPrincipal) -> Response:
    # Another user's device returns 404, not 403: existence is not revealed.
    if not service.revoke_device(principal, device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    return Response(status_code=204)
