"""Login flows: OTP request/verify, trusted-device login, logout, principal lookup (DDR-96–DDR-99).

Transaction boundaries live here. Responses never reveal whether a number is registered: every
OTP request gets the same answer, and every verification failure the same error.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection

from app.core.config import Settings
from app.core.db import get_engine
from app.core.permissions import Portal, Principal
from app.core.request_context import current_request_id
from app.core.security import hashes_match, new_token, otp_hash, token_hash
from app.modules.identity import domain as d
from app.modules.identity import repository as repo
from app.modules.identity.otp_delivery import OtpSender
from app.modules.identity.rate_limit import OtpLimiter


class InvalidCode(Exception):
    """Wrong, expired, exhausted or unknown code: one error for all (no enumeration)."""


class NameRequired(Exception):
    """A new customer must give a name before the account is created (DDR-97)."""


class InvalidMobile(Exception):
    pass


class TrustedLoginFailed(Exception):
    pass


@dataclass(frozen=True)
class IssuedLogin:
    principal: Principal
    session_token: str
    device_token: str | None


def _user_state(conn: Connection, user: repo.UserRow | None) -> d.UserState | None:
    if user is None:
        return None
    return d.UserState(user.status, frozenset(g.role for g in repo.active_grants(conn, user.id)))


def _audit(conn: Connection, action: str, outcome: str, *, user_id: uuid.UUID | None, mobile: str | None,
           portal: Portal, reason: str | None = None) -> None:  # fmt: skip
    repo.write_audit(
        conn,
        action=action,
        outcome=outcome,
        actor_user_id=user_id,
        actor_role="ANONYMOUS" if user_id is None else "USER",
        target_type="user" if user_id else "mobile",
        target_id=str(user_id) if user_id else (d.mask_mobile(mobile) if mobile else None),
        correlation_id=current_request_id(),
        reason=reason,
        after={"portal": portal.value},
    )


def normalize(settings: Settings, raw_mobile: str) -> str:
    mobile = d.normalize_mobile(raw_mobile, allow_test_numbers=settings.is_local_or_test)
    if mobile is None:
        raise InvalidMobile
    return mobile


# ---------------------------------------------------------------- OTP request
def request_otp(
    settings: Settings, limiter: OtpLimiter, sender: OtpSender, raw_mobile: str, portal: Portal, ip: str
) -> None:
    mobile = normalize(settings, raw_mobile)
    limiter.register_request(mobile, portal.value, ip)  # same limits for everyone
    code = sender.new_code()
    with get_engine().begin() as conn:
        user = repo.find_user_by_mobile(conn, mobile)
        decision = d.login_decision(portal, _user_state(conn, user))
        if decision is d.LoginDecision.DENY:
            _audit(conn, "auth.otp_requested", "DENIED", user_id=user.id if user else None, mobile=mobile,
                   portal=portal, reason="not eligible for portal")  # fmt: skip
            return
        repo.retire_open_challenges(conn, mobile, portal)
        repo.create_challenge(
            conn,
            mobile,
            portal,
            otp_hash(code, mobile=mobile, pepper=settings.otp_pepper.get_secret_value()),
            d.OTP_TTL_SECONDS,
            d.OTP_MAX_ATTEMPTS,
        )
        _audit(conn, "auth.otp_requested", "SUCCESS", user_id=user.id if user else None, mobile=mobile,
               portal=portal)  # fmt: skip
    # Send after commit: a delivery failure never leaves a half-written state behind.
    sender.send(mobile, code)


# ---------------------------------------------------------------- OTP verify
def verify_otp(
    settings: Settings,
    limiter: OtpLimiter,
    raw_mobile: str,
    portal: Portal,
    code: str,
    *,
    display_name: str | None,
    trust_device: bool,
    device_label: str | None,
) -> IssuedLogin:
    mobile = normalize(settings, raw_mobile)
    limiter.ensure_not_locked(mobile)
    exhausted = False
    with get_engine().begin() as conn:
        challenge = repo.lock_open_challenge(conn, mobile, portal)
        if challenge is None:
            raise InvalidCode  # nothing written; rollback is harmless
        expected = otp_hash(code, mobile=mobile, pepper=settings.otp_pepper.get_secret_value())
        if hashes_match(expected, challenge.code_hash):
            user = repo.find_user_by_mobile(conn, mobile)
            decision = d.login_decision(portal, _user_state(conn, user))
            if decision is d.LoginDecision.DENY:
                raise InvalidCode
            if decision is d.LoginDecision.REGISTER:
                name = d.clean_display_name(display_name)
                if name is None:
                    raise NameRequired  # nothing consumed: the user resubmits the same code with a name
                user_id = repo.create_customer(conn, mobile, name)
            elif user is not None:
                user_id = user.id
            else:  # ALLOW always has a user; treat anything else as a failed login
                raise InvalidCode
            repo.consume_challenge(conn, challenge.id)
            issued = _issue(conn, user_id, portal, trust_device=trust_device, device_label=device_label)
            _audit(conn, "auth.login", "SUCCESS", user_id=user_id, mobile=None, portal=portal,
                   reason="registered" if decision is d.LoginDecision.REGISTER else None)  # fmt: skip
            return issued
        # Wrong code: the attempt is committed when this block exits normally, then we raise.
        attempts = repo.record_failed_attempt(conn, challenge)
        exhausted = attempts >= challenge.max_attempts
        _audit(conn, "auth.login", "FAILED", user_id=None, mobile=mobile, portal=portal,
               reason="code attempts exhausted" if exhausted else "wrong code")  # fmt: skip
    if exhausted:
        limiter.lock(mobile)
    raise InvalidCode


def _issue(
    conn: Connection,
    user_id: uuid.UUID,
    portal: Portal,
    *,
    trust_device: bool,
    device_label: str | None,
    device_id: uuid.UUID | None = None,
) -> IssuedLogin:
    device_token = None
    if trust_device and device_id is None:
        device_token = new_token()
        label = (device_label or "").strip()[:120] or None
        device_id = repo.create_device(
            conn, user_id, token_hash(device_token), label, d.TRUSTED_DEVICE_SECONDS
        )
    session_token = new_token()
    session_id = repo.create_session(
        conn, user_id, portal, token_hash(session_token), d.SESSION_ABSOLUTE_SECONDS, device_id
    )
    principal = Principal(user_id, repo.active_grants(conn, user_id), session_id)
    return IssuedLogin(principal, session_token, device_token)


# ---------------------------------------------------------------- trusted-device login (DDR-98)
def trusted_login(device_token: str, portal: Portal) -> IssuedLogin:
    with get_engine().begin() as conn:
        device = repo.find_live_device(conn, token_hash(device_token))
        if device is None:
            raise TrustedLoginFailed
        user = repo.find_user(conn, device.user_id)
        if d.login_decision(portal, _user_state(conn, user)) is not d.LoginDecision.ALLOW:
            raise TrustedLoginFailed
        issued = _issue(
            conn, device.user_id, portal, trust_device=False, device_label=None, device_id=device.id
        )
        _audit(conn, "auth.login", "SUCCESS", user_id=device.user_id, mobile=None, portal=portal,
               reason="trusted device")  # fmt: skip
        return issued


# ---------------------------------------------------------------- sessions
def principal_for_session(session_token: str, *, touch: bool = True) -> Principal | None:
    """`touch=False` checks the session without counting as activity (realtime re-validation)."""
    with get_engine().begin() as conn:
        session = repo.find_live_session(conn, token_hash(session_token), d.SESSION_IDLE_SECONDS)
        if session is None:
            return None
        if touch:
            repo.touch_session(conn, session.id)
        return Principal(session.user_id, repo.active_grants(conn, session.user_id), session.id)


def principal_for_user(user_id: uuid.UUID) -> Principal | None:
    """Active grants of an active user, without a session (CLI fixture loader, local/test only)."""
    with get_engine().connect() as conn:
        user = repo.find_user(conn, user_id)
        if user is None or user.status != "ACTIVE":
            return None
        return Principal(user_id, repo.active_grants(conn, user_id))


def logout(principal: Principal) -> None:
    with get_engine().begin() as conn:
        if principal.session_id is not None:
            repo.revoke_session(conn, principal.session_id, "logout")
        repo.write_audit(conn, action="auth.logout", outcome="SUCCESS", actor_user_id=principal.user_id,
                         actor_role="USER", target_type="session", target_id=str(principal.session_id),
                         correlation_id=current_request_id())  # fmt: skip


def list_devices(principal: Principal) -> list[repo.DeviceRow]:
    with get_engine().connect() as conn:
        return repo.list_devices(conn, principal.user_id)


def revoke_device(principal: Principal, device_id: uuid.UUID) -> bool:
    with get_engine().begin() as conn:
        revoked = repo.revoke_device(conn, principal.user_id, device_id, "user_revoked")
        if revoked:
            repo.write_audit(conn, action="auth.device_revoked", outcome="SUCCESS",
                             actor_user_id=principal.user_id, actor_role="USER", target_type="trusted_device",
                             target_id=str(device_id), correlation_id=current_request_id())  # fmt: skip
        return revoked


def display_name(user_id: uuid.UUID) -> str:
    with get_engine().connect() as conn:
        user = repo.find_user(conn, user_id)
        return user.display_name if user else ""
