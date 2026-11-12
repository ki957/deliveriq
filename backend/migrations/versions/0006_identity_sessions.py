"""OTP challenges, sessions and trusted devices; automatic revocation on role or status change.

Sources: PL-02 (hashed, expiring, attempt-limited OTP), PL-04 (role changes revoke sessions),
PL-05 (7-day trusted devices, revocable), DDR-96–DDR-98 (owner-approved parameters).
Only hashes are stored: codes and tokens never reach the database.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PORTALS = "'customer', 'kitchen', 'delivery', 'management'"

UPGRADE_SQL = f"""
CREATE TABLE app.otp_challenges (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile_e164   text NOT NULL,
    portal        text NOT NULL CHECK (portal IN ({PORTALS})),
    code_hash     char(64) NOT NULL,
    attempts      integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts  integer NOT NULL CHECK (max_attempts > 0),
    expires_at    timestamptz NOT NULL,
    consumed_at   timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CHECK (attempts <= max_attempts)
);
CREATE INDEX otp_challenges_open_idx ON app.otp_challenges (mobile_e164, portal, created_at DESC)
    WHERE consumed_at IS NULL;

CREATE TABLE app.trusted_devices (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES app.users (id),
    token_hash     char(64) NOT NULL UNIQUE,
    label          text CHECK (char_length(label) <= 120),
    created_at     timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz NOT NULL,
    revoked_at     timestamptz,
    revoke_reason  text,
    CHECK (expires_at > created_at)
);
CREATE INDEX trusted_devices_user_idx ON app.trusted_devices (user_id) WHERE revoked_at IS NULL;

CREATE TABLE app.sessions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL REFERENCES app.users (id),
    portal             text NOT NULL CHECK (portal IN ({PORTALS})),
    token_hash         char(64) NOT NULL UNIQUE,
    trusted_device_id  uuid REFERENCES app.trusted_devices (id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    last_seen_at       timestamptz NOT NULL DEFAULT now(),
    expires_at         timestamptz NOT NULL,
    revoked_at         timestamptz,
    revoke_reason      text,
    CHECK (expires_at > created_at)
);
CREATE INDEX sessions_user_idx ON app.sessions (user_id) WHERE revoked_at IS NULL;

-- PL-04 / DDR-98: any role change or account status change revokes every session and device of
-- that user, whichever code path made the change.
CREATE FUNCTION app.revoke_user_credentials(p_user uuid, p_reason text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
    UPDATE app.sessions SET revoked_at = now(), revoke_reason = p_reason
     WHERE user_id = p_user AND revoked_at IS NULL;
    UPDATE app.trusted_devices SET revoked_at = now(), revoke_reason = p_reason
     WHERE user_id = p_user AND revoked_at IS NULL;
$$;

CREATE FUNCTION app.revoke_on_role_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    PERFORM app.revoke_user_credentials(
        CASE WHEN TG_OP = 'DELETE' THEN OLD.user_id ELSE NEW.user_id END, 'role_change');
    RETURN NULL;
END $$;

CREATE FUNCTION app.revoke_on_status_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    PERFORM app.revoke_user_credentials(NEW.id, 'status_change');
    RETURN NULL;
END $$;

CREATE TRIGGER role_assignments_revoke AFTER INSERT OR UPDATE OR DELETE ON app.role_assignments
    FOR EACH ROW EXECUTE FUNCTION app.revoke_on_role_change();
CREATE TRIGGER users_status_revoke AFTER UPDATE OF status ON app.users
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION app.revoke_on_status_change();

-- API runtime: no DELETE; revocation is an UPDATE that keeps the record.
GRANT SELECT, INSERT, UPDATE ON app.otp_challenges, app.sessions, app.trusted_devices TO app_api;
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS users_status_revoke ON app.users;
DROP TRIGGER IF EXISTS role_assignments_revoke ON app.role_assignments;
DROP FUNCTION IF EXISTS app.revoke_on_status_change();
DROP FUNCTION IF EXISTS app.revoke_on_role_change();
DROP FUNCTION IF EXISTS app.revoke_user_credentials(uuid, text);
DROP TABLE IF EXISTS app.sessions;
DROP TABLE IF EXISTS app.trusted_devices;
DROP TABLE IF EXISTS app.otp_challenges;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
