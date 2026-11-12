"""SQL for identity tables. Parameterised queries only; callers own the transaction."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text

from app.core.permissions import Grant, Portal, Role


@dataclass(frozen=True)
class UserRow:
    id: uuid.UUID
    display_name: str
    status: str


@dataclass(frozen=True)
class ChallengeRow:
    id: uuid.UUID
    code_hash: str
    attempts: int
    max_attempts: int


@dataclass(frozen=True)
class SessionRow:
    id: uuid.UUID
    user_id: uuid.UUID
    portal: str
    last_seen_at: datetime


@dataclass(frozen=True)
class DeviceRow:
    id: uuid.UUID
    user_id: uuid.UUID
    label: str | None
    created_at: datetime
    expires_at: datetime


# ---------------------------------------------------------------- users and roles
def find_user_by_mobile(conn: Connection, mobile: str) -> UserRow | None:
    row = conn.execute(
        text("SELECT id, display_name, status FROM app.users WHERE mobile_e164 = :m"), {"m": mobile}
    ).first()
    return UserRow(*row) if row else None


def find_user(conn: Connection, user_id: uuid.UUID) -> UserRow | None:
    row = conn.execute(
        text("SELECT id, display_name, status FROM app.users WHERE id = :id"), {"id": user_id}
    ).first()
    return UserRow(*row) if row else None


def active_grants(conn: Connection, user_id: uuid.UUID) -> tuple[Grant, ...]:
    rows = conn.execute(
        text(
            "SELECT role, region_id, kitchen_id FROM app.role_assignments "
            "WHERE user_id = :u AND revoked_at IS NULL ORDER BY role"
        ),
        {"u": user_id},
    ).all()
    return tuple(Grant(Role(r.role), r.region_id, r.kitchen_id) for r in rows)


def create_customer(conn: Connection, mobile: str, display_name: str) -> uuid.UUID:
    user_id: uuid.UUID = conn.execute(
        text("INSERT INTO app.users (display_name, mobile_e164) VALUES (:n, :m) RETURNING id"),
        {"n": display_name, "m": mobile},
    ).scalar_one()
    conn.execute(
        text("INSERT INTO app.role_assignments (user_id, role) VALUES (:u, 'CUSTOMER')"), {"u": user_id}
    )
    return user_id


# ---------------------------------------------------------------- OTP challenges
def retire_open_challenges(conn: Connection, mobile: str, portal: Portal) -> None:
    conn.execute(
        text(
            "UPDATE app.otp_challenges SET consumed_at = now() "
            "WHERE mobile_e164 = :m AND portal = :p AND consumed_at IS NULL"
        ),
        {"m": mobile, "p": portal.value},
    )


def create_challenge(
    conn: Connection, mobile: str, portal: Portal, code_hash: str, ttl_seconds: int, max_attempts: int
) -> None:
    conn.execute(
        text(
            "INSERT INTO app.otp_challenges (mobile_e164, portal, code_hash, max_attempts, expires_at) "
            "VALUES (:m, :p, :h, :a, now() + make_interval(secs => :ttl))"
        ),
        {"m": mobile, "p": portal.value, "h": code_hash, "a": max_attempts, "ttl": ttl_seconds},
    )


def lock_open_challenge(conn: Connection, mobile: str, portal: Portal) -> ChallengeRow | None:
    row = conn.execute(
        text(
            "SELECT id, code_hash, attempts, max_attempts FROM app.otp_challenges "
            "WHERE mobile_e164 = :m AND portal = :p AND consumed_at IS NULL AND expires_at > now() "
            "ORDER BY created_at DESC LIMIT 1 FOR UPDATE"
        ),
        {"m": mobile, "p": portal.value},
    ).first()
    return ChallengeRow(*row) if row else None


def record_failed_attempt(conn: Connection, challenge: ChallengeRow) -> int:
    attempts: int = conn.execute(
        text(
            "UPDATE app.otp_challenges SET attempts = attempts + 1, "
            "consumed_at = CASE WHEN attempts + 1 >= max_attempts THEN now() END "
            "WHERE id = :id RETURNING attempts"
        ),
        {"id": challenge.id},
    ).scalar_one()
    return attempts


def consume_challenge(conn: Connection, challenge_id: uuid.UUID) -> None:
    conn.execute(
        text("UPDATE app.otp_challenges SET consumed_at = now() WHERE id = :id"), {"id": challenge_id}
    )


# ---------------------------------------------------------------- sessions
def create_session(
    conn: Connection,
    user_id: uuid.UUID,
    portal: Portal,
    token_hash: str,
    absolute_seconds: int,
    device_id: uuid.UUID | None,
) -> uuid.UUID:
    session_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.sessions (user_id, portal, token_hash, trusted_device_id, expires_at) "
            "VALUES (:u, :p, :h, :d, now() + make_interval(secs => :s)) RETURNING id"
        ),
        {"u": user_id, "p": portal.value, "h": token_hash, "d": device_id, "s": absolute_seconds},
    ).scalar_one()
    return session_id


def find_live_session(conn: Connection, token_hash: str, idle_seconds: int) -> SessionRow | None:
    row = conn.execute(
        text(
            "SELECT s.id, s.user_id, s.portal, s.last_seen_at FROM app.sessions s "
            "JOIN app.users u ON u.id = s.user_id "
            "WHERE s.token_hash = :h AND s.revoked_at IS NULL AND s.expires_at > now() "
            "AND s.last_seen_at > now() - make_interval(secs => :idle) AND u.status = 'ACTIVE'"
        ),
        {"h": token_hash, "idle": idle_seconds},
    ).first()
    return SessionRow(*row) if row else None


def touch_session(conn: Connection, session_id: uuid.UUID) -> None:
    conn.execute(
        text(
            "UPDATE app.sessions SET last_seen_at = now() "
            "WHERE id = :id AND last_seen_at < now() - interval '60 seconds'"
        ),
        {"id": session_id},
    )


def revoke_session(conn: Connection, session_id: uuid.UUID, reason: str) -> None:
    conn.execute(
        text(
            "UPDATE app.sessions SET revoked_at = now(), revoke_reason = :r "
            "WHERE id = :id AND revoked_at IS NULL"
        ),
        {"id": session_id, "r": reason},
    )


# ---------------------------------------------------------------- trusted devices
def create_device(
    conn: Connection, user_id: uuid.UUID, token_hash: str, label: str | None, ttl: int
) -> uuid.UUID:
    device_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.trusted_devices (user_id, token_hash, label, expires_at) "
            "VALUES (:u, :h, :l, now() + make_interval(secs => :t)) RETURNING id"
        ),
        {"u": user_id, "h": token_hash, "l": label, "t": ttl},
    ).scalar_one()
    return device_id


def find_live_device(conn: Connection, token_hash: str) -> DeviceRow | None:
    row = conn.execute(
        text(
            "SELECT id, user_id, label, created_at, expires_at FROM app.trusted_devices "
            "WHERE token_hash = :h AND revoked_at IS NULL AND expires_at > now()"
        ),
        {"h": token_hash},
    ).first()
    return DeviceRow(*row) if row else None


def list_devices(conn: Connection, user_id: uuid.UUID) -> list[DeviceRow]:
    rows = conn.execute(
        text(
            "SELECT id, user_id, label, created_at, expires_at FROM app.trusted_devices "
            "WHERE user_id = :u AND revoked_at IS NULL AND expires_at > now() ORDER BY created_at DESC"
        ),
        {"u": user_id},
    ).all()
    return [DeviceRow(*r) for r in rows]


def revoke_device(conn: Connection, user_id: uuid.UUID, device_id: uuid.UUID, reason: str) -> bool:
    """Revoke a device owned by user_id and any session opened with it. False if not found."""
    result = conn.execute(
        text(
            "UPDATE app.trusted_devices SET revoked_at = now(), revoke_reason = :r "
            "WHERE id = :id AND user_id = :u AND revoked_at IS NULL"
        ),
        {"id": device_id, "u": user_id, "r": reason},
    )
    if result.rowcount == 0:
        return False
    conn.execute(
        text(
            "UPDATE app.sessions SET revoked_at = now(), revoke_reason = :r "
            "WHERE trusted_device_id = :id AND revoked_at IS NULL"
        ),
        {"id": device_id, "r": reason},
    )
    return True


# ---------------------------------------------------------------- audit (PL-12, DDR-99)
def write_audit(
    conn: Connection,
    *,
    action: str,
    outcome: str,
    actor_user_id: uuid.UUID | None,
    actor_role: str,
    target_type: str,
    target_id: str | None,
    correlation_id: str | None,
    reason: str | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO audit.events (actor_user_id, actor_role, action, target_type, target_id, outcome, "
            "reason, correlation_id, after_summary) "
            "VALUES (:actor, :role, :action, :ttype, :tid, :outcome, :reason, :cid, CAST(:after AS jsonb))"
        ),
        {
            "actor": actor_user_id,
            "role": actor_role,
            "action": action,
            "ttype": target_type,
            "tid": target_id,
            "outcome": outcome,
            "reason": reason,
            "cid": correlation_id,
            "after": None if after is None else json.dumps(after),
        },
    )
