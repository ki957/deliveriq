"""Login, sessions, trusted devices and the negative authorization matrix over real HTTP.

Needs the core stack with APP_ENV=local or test and OTP_ADAPTER=mock (`make up`,
`make test-integration`). Test users, a second region and a second kitchen are created through
the migrator role and removed afterwards; audit rows stay (append-only) and hold masked numbers.
"""

from __future__ import annotations

import os
import random
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import psycopg
import pytest

from app.modules.identity.otp_delivery import MOCK_OTP_CODE

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running core stack"),
]

CSRF = {"X-DeliverIQ-CSRF": "1"}
API = os.environ.get("INTEGRATION_API_URL", "http://127.0.0.1:8000")


def _db() -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user="app_migrator",
        password=os.environ["APP_MIGRATOR_PASSWORD"],
        autocommit=True,
    )


@dataclass
class World:
    db: psycopg.Connection[tuple[object, ...]]
    prefix: str
    region_a: uuid.UUID
    kitchen_a: uuid.UUID
    region_b: uuid.UUID
    kitchen_b: uuid.UUID
    counter: int = 0
    users: list[uuid.UUID] | None = None
    mobiles: list[str] | None = None

    def mobile(self) -> str:
        # Skip numbers already in use (e.g. left by an interrupted earlier run), so prefixes never collide.
        while True:
            self.counter += 1
            number = f"+9100000{self.prefix}{self.counter:02d}"
            taken = self.db.execute("SELECT 1 FROM app.users WHERE mobile_e164 = %s", (number,)).fetchone()
            if taken is None:
                break
        assert self.mobiles is not None
        self.mobiles.append(number)
        return number

    def user(
        self, role: str | None, *, region: uuid.UUID | None = None, kitchen: uuid.UUID | None = None
    ) -> str:
        mobile = self.mobile()
        row = self.db.execute(
            "INSERT INTO app.users (display_name, mobile_e164) VALUES ('Integration user', %s) RETURNING id",
            (mobile,),
        ).fetchone()
        assert row is not None and self.users is not None
        self.users.append(row[0])  # type: ignore[arg-type]
        if role:
            self.db.execute(
                "INSERT INTO app.role_assignments (user_id, role, region_id, kitchen_id) VALUES (%s, %s, %s, %s)",
                (row[0], role, region, kitchen),
            )
        return mobile


@pytest.fixture(scope="module")
def world() -> Iterator[World]:
    db = _db()
    # A free code: an interrupted earlier run may have left its REG-TST/KIT-TST rows behind.
    used = {
        str(row[0])[-3:]
        for row in db.execute(
            "SELECT code FROM app.regions WHERE code LIKE 'REG-TST-%' "
            "UNION SELECT code FROM app.kitchens WHERE code LIKE 'KIT-TST-%'"
        )
    }
    free = [f"{n}" for n in range(100, 1000) if f"{n}" not in used]
    assert free, "every REG-TST code is taken; delete stale integration regions"
    prefix = random.choice(free)  # noqa: S311 - test data, not security
    a = db.execute("SELECT id, region_id FROM app.kitchens WHERE code = 'KIT-CHN-001'").fetchone()
    assert a is not None
    region_b = db.execute(
        "INSERT INTO app.regions (code, name, city, state, country, timezone, status) "
        "VALUES (%s, 'Integration region', 'Test', 'Test', 'India', 'Asia/Kolkata', 'ACTIVE') RETURNING id",
        (f"REG-TST-{prefix}",),
    ).fetchone()
    assert region_b is not None
    kitchen_b = db.execute(
        "INSERT INTO app.kitchens (code, region_id, name, address, location, location_is_synthetic, status) "
        "VALUES (%s, %s, 'Integration kitchen', 'Synthetic', ST_MakePoint(80, 13)::geography, true, 'ACTIVE') "
        "RETURNING id",
        (f"KIT-TST-{prefix}", region_b[0]),
    ).fetchone()
    assert kitchen_b is not None
    w = World(db, prefix, a[1], a[0], region_b[0], kitchen_b[0], users=[], mobiles=[])  # type: ignore[arg-type]
    try:
        yield w
    finally:
        mobiles = w.mobiles or []
        ids = [u for (u,) in db.execute("SELECT id FROM app.users WHERE mobile_e164 = ANY(%s)", (mobiles,))]
        db.execute("DELETE FROM app.role_assignments WHERE user_id = ANY(%s)", (ids,))
        db.execute("DELETE FROM app.sessions WHERE user_id = ANY(%s)", (ids,))
        db.execute("DELETE FROM app.trusted_devices WHERE user_id = ANY(%s)", (ids,))
        db.execute("DELETE FROM app.otp_challenges WHERE mobile_e164 = ANY(%s)", (mobiles,))
        db.execute("DELETE FROM app.users WHERE id = ANY(%s)", (ids,))
        db.execute("DELETE FROM app.kitchens WHERE id = %s", (w.kitchen_b,))
        db.execute("DELETE FROM app.regions WHERE id = %s", (w.region_b,))
        db.close()


def client() -> httpx.Client:
    return httpx.Client(base_url=API, headers=CSRF, timeout=10)


def reset_limits() -> None:
    with client() as c:
        assert c.post("/api/v1/_test/reset-otp-limits").status_code == 204


def request_code(c: httpx.Client, mobile: str, portal: str) -> httpx.Response:
    reset_limits()
    return c.post("/api/v1/auth/otp/request", json={"mobile": mobile, "portal": portal})


def login(mobile: str, portal: str, **extra: object) -> httpx.Client:
    c = client()
    assert request_code(c, mobile, portal).status_code == 202
    response = c.post("/api/v1/auth/otp/verify",
                      json={"mobile": mobile, "portal": portal, "code": MOCK_OTP_CODE, **extra})  # fmt: skip
    assert response.status_code == 200, response.text
    return c


# ---------------------------------------------------------------- OTP and registration
def test_request_answer_is_identical_for_unknown_and_known_numbers(world: World) -> None:
    known = world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a)
    with client() as c:
        a = request_code(c, known, "kitchen")
        b = request_code(c, world.mobile(), "kitchen")  # unknown staff number
    assert a.status_code == b.status_code == 202
    assert a.json() == b.json() == {"status": "sent_if_eligible", "expires_in_seconds": 300,
                                    "resend_after_seconds": 30}  # fmt: skip


def test_new_customer_registers_after_otp_with_name(world: World) -> None:
    mobile = world.mobile()
    with client() as c:
        request_code(c, mobile, "customer")
        body = {"mobile": mobile, "portal": "customer", "code": MOCK_OTP_CODE}
        assert c.post("/api/v1/auth/otp/verify", json=body).status_code == 422  # name required
        ok = c.post("/api/v1/auth/otp/verify", json={**body, "display_name": "Asha"})
        assert ok.status_code == 200, ok.text
        me = c.get("/api/v1/me").json()
    assert me["display_name"] == "Asha"
    assert [g["role"] for g in me["roles"]] == ["CUSTOMER"]
    assert me["portals"] == ["customer"]
    assert "diq_session" in ok.headers["set-cookie"] and "HttpOnly" in ok.headers["set-cookie"]


def test_otp_is_stored_only_as_a_hash(world: World) -> None:
    mobile = world.user("CUSTOMER")
    with client() as c:
        request_code(c, mobile, "customer")
    row = world.db.execute(
        "SELECT code_hash, expires_at - created_at FROM app.otp_challenges WHERE mobile_e164 = %s "
        "ORDER BY created_at DESC LIMIT 1",
        (mobile,),
    ).fetchone()
    assert row is not None
    assert row[0] != MOCK_OTP_CODE and len(str(row[0])) == 64
    assert row[1].total_seconds() == 300  # type: ignore[attr-defined]


def test_unknown_number_cannot_log_in_to_staff_portal(world: World) -> None:
    mobile = world.mobile()
    with client() as c:
        request_code(c, mobile, "management")
        r = c.post(
            "/api/v1/auth/otp/verify", json={"mobile": mobile, "portal": "management", "code": MOCK_OTP_CODE}
        )
    assert r.status_code == 400
    assert world.db.execute(
        "SELECT count(*) FROM app.users WHERE mobile_e164 = %s", (mobile,)
    ).fetchone() == (0,)


def test_staff_without_customer_role_cannot_use_customer_portal(world: World) -> None:
    mobile = world.user("KITCHEN_MANAGER", region=world.region_a, kitchen=world.kitchen_a)
    with client() as c:
        request_code(c, mobile, "customer")
        r = c.post("/api/v1/auth/otp/verify",
                   json={"mobile": mobile, "portal": "customer", "code": MOCK_OTP_CODE, "display_name": "X"})  # fmt: skip
    assert r.status_code == 400


def test_five_wrong_codes_exhaust_the_challenge_and_lock(world: World) -> None:
    mobile = world.user("CUSTOMER")
    with client() as c:
        request_code(c, mobile, "customer")
        body = {"mobile": mobile, "portal": "customer"}
        for _ in range(5):
            assert c.post("/api/v1/auth/otp/verify", json={**body, "code": "000000"}).status_code == 400
        locked = c.post("/api/v1/auth/otp/verify", json={**body, "code": MOCK_OTP_CODE})
        assert locked.status_code == 429
        assert int(locked.headers["Retry-After"]) > 0
    reset_limits()


def test_resend_cooldown(world: World) -> None:
    mobile = world.user("CUSTOMER")
    with client() as c:
        assert request_code(c, mobile, "customer").status_code == 202
        again = c.post("/api/v1/auth/otp/request", json={"mobile": mobile, "portal": "customer"})
    assert again.status_code == 429
    assert 0 < int(again.headers["Retry-After"]) <= 30


def test_invalid_number_rejected(world: World) -> None:
    with client() as c:
        r = c.post("/api/v1/auth/otp/request", json={"mobile": "+1 415 555 0100", "portal": "customer"})
    assert r.status_code == 422


# ---------------------------------------------------------------- CSRF and sessions
def test_unsafe_request_without_csrf_header_is_refused(world: World) -> None:
    with httpx.Client(base_url=API) as c:
        r = c.post("/api/v1/auth/otp/request", json={"mobile": world.mobile(), "portal": "customer"})
    assert r.status_code == 403


def test_me_requires_a_session() -> None:
    with client() as c:
        assert c.get("/api/v1/me").status_code == 401


def test_logout_revokes_the_session(world: World) -> None:
    c = login(world.user("CUSTOMER"), "customer")
    assert c.get("/api/v1/me").status_code == 200
    assert c.post("/api/v1/auth/logout").status_code == 204
    token = c.cookies.get("diq_session")
    assert token is None or c.get("/api/v1/me").status_code == 401
    c.close()


def test_role_removal_revokes_sessions_immediately(world: World) -> None:
    mobile = world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a)
    c = login(mobile, "kitchen")
    assert c.get("/api/v1/me").status_code == 200
    world.db.execute(
        "UPDATE app.role_assignments SET revoked_at = now() "
        "WHERE user_id = (SELECT id FROM app.users WHERE mobile_e164 = %s)",
        (mobile,),
    )
    assert c.get("/api/v1/me").status_code == 401
    c.close()


def test_deactivation_revokes_sessions(world: World) -> None:
    mobile = world.user("CUSTOMER")
    c = login(mobile, "customer")
    world.db.execute("UPDATE app.users SET status = 'DEACTIVATED' WHERE mobile_e164 = %s", (mobile,))
    assert c.get("/api/v1/me").status_code == 401
    c.close()


# ---------------------------------------------------------------- trusted devices (DDR-98)
def test_trusted_device_skips_otp_until_revoked(world: World) -> None:
    mobile = world.user("CUSTOMER")
    c = login(mobile, "customer", trust_device=True, device_label="Test laptop")
    device_cookie = c.cookies.get("diq_device")
    assert device_cookie
    devices = c.get("/api/v1/me/devices").json()
    assert [d["label"] for d in devices] == ["Test laptop"]
    lifetime = world.db.execute(
        "SELECT expires_at - created_at FROM app.trusted_devices WHERE id = %s", (devices[0]["id"],)
    ).fetchone()
    assert lifetime is not None and lifetime[0].total_seconds() == 7 * 24 * 3600  # type: ignore[attr-defined]

    with client() as fresh:
        fresh.cookies.set("diq_device", device_cookie)
        assert fresh.post("/api/v1/auth/trusted-login", json={"portal": "customer"}).status_code == 200
        assert fresh.get("/api/v1/me").status_code == 200
        # The device does not open other portals.
        assert fresh.post("/api/v1/auth/trusted-login", json={"portal": "kitchen"}).status_code == 401

    other = login(world.user("CUSTOMER"), "customer")
    assert other.delete(f"/api/v1/me/devices/{devices[0]['id']}").status_code == 404  # not theirs
    other.close()

    assert c.delete(f"/api/v1/me/devices/{devices[0]['id']}").status_code == 204
    with client() as fresh:
        fresh.cookies.set("diq_device", device_cookie)
        assert fresh.post("/api/v1/auth/trusted-login", json={"portal": "customer"}).status_code == 401
    c.close()


# ---------------------------------------------------------------- negative matrix (Phase 2 §8.5)
def check(c: httpx.Client, permission: str, **scope: object) -> int:
    params = {"permission": permission, **{k: str(v) for k, v in scope.items()}}
    return c.get("/api/v1/_test/scope-check", params=params).status_code


def test_cross_customer(world: World) -> None:
    a = login(world.user("CUSTOMER"), "customer")
    b = login(world.user("CUSTOMER"), "customer")
    a_id, b_id = a.get("/api/v1/me").json()["user_id"], b.get("/api/v1/me").json()["user_id"]
    assert check(a, "customer.orders.read", customer_id=a_id) == 200
    assert check(a, "customer.orders.read", customer_id=b_id) == 403
    a.close()
    b.close()


def test_cross_kitchen(world: World) -> None:
    staff = login(world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a), "kitchen")
    assert check(staff, "kitchen.orders.view", kitchen_id=world.kitchen_a) == 200
    assert check(staff, "kitchen.orders.view", kitchen_id=world.kitchen_b) == 403
    staff.close()


def test_cross_region(world: World) -> None:
    rm = login(world.user("REGIONAL_MANAGER", region=world.region_a), "management")
    assert check(rm, "menu.publish", region_id=world.region_a) == 200
    assert check(rm, "menu.publish", region_id=world.region_b) == 403
    rm.close()


def test_kitchen_staff_cannot_use_manager_only_actions(world: World) -> None:
    staff = login(world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a), "kitchen")
    manager = login(world.user("KITCHEN_MANAGER", region=world.region_a, kitchen=world.kitchen_a), "kitchen")
    for permission in ("kitchen.stock.adjust", "kitchen.recipes.activate", "kitchen.mode.change"):
        assert check(staff, permission, kitchen_id=world.kitchen_a) == 403
        assert check(manager, permission, kitchen_id=world.kitchen_a) == 200
    staff.close()
    manager.close()


def test_regional_manager_cannot_use_central_admin_actions(world: World) -> None:
    rm = login(world.user("REGIONAL_MANAGER", region=world.region_a), "management")
    ca = login(world.user("CENTRAL_ADMIN"), "management")
    for permission in ("management.settings.global", "management.regional_managers.manage"):
        assert check(rm, permission, region_id=world.region_a) == 403
        assert check(ca, permission) == 200
    assert check(ca, "menu.publish", region_id=world.region_b) == 200  # CA is global
    rm.close()
    ca.close()


def test_portal_login_requires_matching_role(world: World) -> None:
    mobile = world.user("DELIVERY_AGENT", region=world.region_a)
    with client() as c:
        request_code(c, mobile, "management")
        r = c.post(
            "/api/v1/auth/otp/verify", json={"mobile": mobile, "portal": "management", "code": MOCK_OTP_CODE}
        )
    assert r.status_code == 400
