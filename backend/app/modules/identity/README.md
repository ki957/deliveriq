# Identity module

**Purpose and scope:** mobile OTP login, sessions, trusted devices and the current principal for all four portals (PL-02–PL-06, DDR-96–DDR-99). Lost-mobile recovery is **not built** (DDR-41, open).

| Item | Value |
|---|---|
| UI screens | Shared login page per portal (Task 4B) |
| API endpoints | `POST /api/v1/auth/otp/request` (202, same body for every accepted request) · `POST /api/v1/auth/otp/verify` (sets `diq_session`, optional `diq_device`) · `POST /api/v1/auth/trusted-login` · `POST /api/v1/auth/logout` · `GET /api/v1/me` · `GET /api/v1/me/devices` · `DELETE /api/v1/me/devices/{id}` |
| Test-only endpoints | `GET /api/v1/_test/scope-check`, `POST /api/v1/_test/reset-otp-limits`, mounted only when `APP_ENV` is local or test; not in the committed OpenAPI |
| Service functions | `request_otp`, `verify_otp`, `trusted_login`, `principal_for_session`, `logout`, `list_devices`, `revoke_device` |
| Tables | `app.otp_challenges`, `app.sessions`, `app.trusted_devices` (migration 0006); `app.users`, `app.role_assignments`; `audit.events` |
| Permissions | Public: OTP request/verify, trusted login. Authenticated: logout, `/me`. Scope guard `app.core.permissions.can()` is used by every later module |
| States | 202 accepted · 400 invalid or expired code · 401 no session · 403 missing CSRF header · 404 device not yours · 422 bad number / `name_required` · 429 limits (with `Retry-After`) · 503 no OTP channel or Redis down (fail closed) |
| Tests | `tests/test_domain.py`, `test_rate_limit.py`, `test_otp_delivery.py` (unit); `test_auth_integration.py` (HTTP + DB: registration, limits, CSRF, revocation, trusted devices, negative matrix); `core/tests/test_permissions.py` |

## Rules implemented

- **OTP (DDR-96):** 6 digits, 5-minute expiry, 5 attempts per code then a 15-minute lockout, 30 s resend cooldown, 5 per mobile and 20 per IP per 15 minutes. Only an HMAC-SHA256 hash (`OTP_PEPPER`) is stored; codes are never logged. `OTP_ADAPTER=mock` (fixed `123456`) is refused outside local/test; production uses `disabled` and fails closed (no SMS provider, DDR-40).
- **No enumeration (DDR-97):** every accepted request gets the same 202 body, limits apply to every number, and every verification failure returns the same 400.
- **Registration (DDR-97):** only the customer portal creates accounts, after OTP verification and with a name. Staff need a matching role; staff never become customers implicitly (PL-03).
- **Sessions (DDR-98):** opaque token in an HttpOnly, SameSite=Lax cookie (Secure in production); only its SHA-256 is stored; 2 h idle, 24 h absolute.
- **Trusted devices (DDR-98):** 7 days from creation, not sliding; works only for portals the user may enter; revoking a device also ends sessions opened with it.
- **Revocation (PL-04):** a database trigger revokes all sessions and devices on any role or status change, whichever code path makes it.
- **CSRF:** unsafe methods require `X-DeliverIQ-CSRF: 1`.

## Assumptions and integration points

- Staff accounts come from the local/test fixture loader (`make fixtures`) until the Management staff screens (Task 10).
- Expired OTP challenges and sessions are kept. A daily worker job (`app.purge_auth(30)`, `notifications` module README) deletes them 30 days after expiry or revocation, audited (DDR-115 (12), closing DDR-107 (8)). Realtime sockets re-validate the session without counting as activity (`principal_for_session(touch=False)`, DDR-115 (7)).
