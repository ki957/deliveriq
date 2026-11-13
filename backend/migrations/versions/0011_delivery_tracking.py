"""Delivery assignment lifecycle, delivery OTP and GPS tracking (Task 9A; DDR-14, DDR-43, DDR-51, DDR-52,
DDR-78, DDR-113).

Sources: #7 §3 (online/offline, 60-second offers, pool, one active delivery, manager override and
force-offline), §5 (pickup, six-digit OTP verified by the backend), §6 (GPS from assignment, stale and
out-of-order points rejected), §7 (customer unavailable, refusal, failure approved by the manager),
DL-01–DL-15, DL-G1–DL-G5, DDR-113.

- `app.agent_availability`: an agent without a row is OFFLINE; only ONLINE agents get offers.
- `app.offer_next(order)`: the one re-offer rule (DDR-113 (3), (17)), used by kitchen acceptance and the
  worker sweep `app.expire_and_reoffer()`. Retention: `app.purge_delivery_locations(days)`. The worker
  role gets EXECUTE on the two job functions only, never table grants (DDR-113 (17)).
- `app.delivery_otps`: the code itself is never stored; it is derived from a random nonce with the server
  secret, so the database alone cannot reveal it (DDR-113 (6)).
- `app.delivery_locations`: points per assignment, REAL or SIMULATED, fixture flag derived from the order.
- New transition FAILURE_REQUESTED → ACCEPTED (manager rejects a failure request; DDR-113 (18)).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
INSERT INTO app.status_transitions (machine, from_status, to_status, reason_required, allowed_roles, source_ref)
VALUES ('assignment', 'FAILURE_REQUESTED', 'ACCEPTED', true, ARRAY['REGIONAL_MANAGER', 'CENTRAL_ADMIN'],
        'DA-18; DDR-113 (18) manager rejects the failure request');

-- Stale GPS points are refused after this many seconds (DDR-113 (8); test default, not defined in sources).
INSERT INTO app.config_settings (key, value, unit, scope_type, is_test_default, source_ref)
VALUES ('GPS_STALE_SECONDS', 120, 'seconds', 'GLOBAL', true, '#7 §6 "stale updates"; DDR-113 (8) test default');

-- ---------------------------------------------------------------- agent availability (DL-01, DL-06)
CREATE TABLE app.agent_availability (
    agent_user_id  uuid PRIMARY KEY REFERENCES app.users (id),
    status         text NOT NULL CHECK (status IN ('ONLINE', 'OFFLINE')),
    changed_at     timestamptz NOT NULL DEFAULT now(),
    changed_by     uuid NOT NULL REFERENCES app.users (id),
    reason         text CHECK (char_length(reason) <= 500)
);

-- ---------------------------------------------------------------- customer unavailable wait (DDR-14)
ALTER TABLE app.orders ADD COLUMN customer_unavailable_since timestamptz;

-- ---------------------------------------------------------------- delivery OTP (DL-11; DDR-113 (6))
CREATE TABLE app.delivery_otps (
    order_id         uuid PRIMARY KEY,
    -- Random value; the six digits are HMAC(server secret, order and nonce) and are never stored.
    nonce            text NOT NULL CHECK (char_length(nonce) >= 32),
    failed_attempts  integer NOT NULL DEFAULT 0 CHECK (failed_attempts BETWEEN 0 AND 3),
    issued_at        timestamptz NOT NULL DEFAULT now(),
    issued_by        uuid,
    verified_at      timestamptz,
    is_test_fixture  boolean NOT NULL DEFAULT false,
    FOREIGN KEY (order_id, is_test_fixture) REFERENCES app.orders (id, is_test_fixture)
);

-- ---------------------------------------------------------------- GPS points (DL-G1–DL-G5; DDR-52, DDR-78)
CREATE TABLE app.delivery_locations (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id    uuid NOT NULL REFERENCES app.delivery_assignments (id),
    order_id         uuid NOT NULL,
    agent_user_id    uuid NOT NULL,
    location         geography(Point, 4326) NOT NULL,
    accuracy_m       numeric(8, 2) CHECK (accuracy_m >= 0),
    recorded_at      timestamptz NOT NULL,
    received_at      timestamptz NOT NULL DEFAULT now(),
    source           text NOT NULL CHECK (source IN ('REAL', 'SIMULATED')),
    is_test_fixture  boolean NOT NULL DEFAULT false,
    FOREIGN KEY (order_id, is_test_fixture) REFERENCES app.orders (id, is_test_fixture)
);
CREATE INDEX delivery_locations_assignment_idx ON app.delivery_locations (assignment_id, recorded_at DESC);
CREATE INDEX delivery_locations_received_idx ON app.delivery_locations (received_at);

CREATE FUNCTION app.inherit_order_flag_by_order_id() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    SELECT o.is_test_fixture INTO NEW.is_test_fixture FROM app.orders o WHERE o.id = NEW.order_id;
    RETURN NEW;
END $$;
CREATE TRIGGER a_delivery_otps_fixture BEFORE INSERT ON app.delivery_otps
    FOR EACH ROW EXECUTE FUNCTION app.inherit_order_flag_by_order_id();
CREATE TRIGGER b_delivery_otps_keep_flag BEFORE UPDATE ON app.delivery_otps
    FOR EACH ROW EXECUTE FUNCTION app.keep_fixture_flag();
CREATE TRIGGER a_delivery_locations_fixture BEFORE INSERT ON app.delivery_locations
    FOR EACH ROW EXECUTE FUNCTION app.inherit_order_flag_by_order_id();

-- ---------------------------------------------------------------- the re-offer rule (DDR-113 (3), (4), (17))
-- Offer an order the kitchen holds to the next eligible agent: active, DELIVERY_AGENT in the order's
-- region, ONLINE, no open offer or live delivery, and never an agent who already rejected or let this
-- order expire. Least recently offered first. Returns the assignment id, or NULL ("Awaiting agent").
-- Runs with the caller's actor context; SYSTEM when none is set (the worker sweep).
CREATE FUNCTION app.offer_next(p_order uuid) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    v_region  uuid;
    v_agent   uuid;
    v_id      uuid;
BEGIN
    SELECT o.region_id INTO v_region FROM app.orders o
     WHERE o.id = p_order AND o.fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP');
    IF v_region IS NULL OR EXISTS (SELECT 1 FROM app.delivery_assignments a WHERE a.order_id = p_order
                                     AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')) THEN
        RETURN NULL;
    END IF;
    IF nullif(current_setting('app.actor_role', true), '') IS NULL THEN
        PERFORM set_config('app.actor_role', 'SYSTEM', true), set_config('app.actor_user_id', '', true);
    END IF;
    SELECT u.id INTO v_agent FROM app.users u
      JOIN app.agent_availability av ON av.agent_user_id = u.id AND av.status = 'ONLINE'
     WHERE u.status = 'ACTIVE'
       AND EXISTS (SELECT 1 FROM app.role_assignments r WHERE r.user_id = u.id AND r.role = 'DELIVERY_AGENT'
                     AND r.region_id = v_region AND r.revoked_at IS NULL)
       AND NOT EXISTS (SELECT 1 FROM app.delivery_assignments a WHERE a.agent_user_id = u.id
                         AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED'))
       AND NOT EXISTS (SELECT 1 FROM app.delivery_assignments a WHERE a.agent_user_id = u.id
                         AND a.order_id = p_order AND a.status IN ('REJECTED', 'EXPIRED'))
     ORDER BY (SELECT max(a.offered_at) FROM app.delivery_assignments a WHERE a.agent_user_id = u.id)
              NULLS FIRST, u.id
     LIMIT 1 FOR UPDATE OF u SKIP LOCKED;
    IF v_agent IS NULL THEN
        RETURN NULL;
    END IF;
    BEGIN
        INSERT INTO app.delivery_assignments (order_id, agent_user_id, status)
        VALUES (p_order, v_agent, 'OFFERED') RETURNING id INTO v_id;
    EXCEPTION WHEN unique_violation THEN
        RETURN NULL;  -- a concurrent offer took the agent or the order first
    END;
    RETURN v_id;
END $$;

-- Worker sweep (DDR-113 (2)): expire offers older than the region's response timeout, then offer every
-- order the kitchen holds that has no live assignment. Returns the number of offers expired.
CREATE FUNCTION app.expire_and_reoffer() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    v_expired  integer;
    v_order    uuid;
BEGIN
    PERFORM set_config('app.actor_role', 'SYSTEM', true), set_config('app.actor_user_id', '', true),
            set_config('app.reason', 'Offer response timeout (DL-04)', true);
    UPDATE app.delivery_assignments a SET status = 'EXPIRED', responded_at = now()
      FROM app.orders o
     WHERE a.status = 'OFFERED' AND o.id = a.order_id
       AND a.offered_at < now() - make_interval(secs => coalesce(
             (SELECT c.value FROM app.config_settings c WHERE c.key = 'AGENT_ASSIGNMENT_RESPONSE_TIMEOUT'
                AND c.scope_type = 'REGION' AND c.region_id = o.region_id),
             (SELECT c.value FROM app.config_settings c WHERE c.key = 'AGENT_ASSIGNMENT_RESPONSE_TIMEOUT'
                AND c.scope_type = 'GLOBAL'), 60)::double precision);
    GET DIAGNOSTICS v_expired = ROW_COUNT;
    FOR v_order IN
        SELECT o.id FROM app.orders o
         WHERE o.fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP')
           AND NOT EXISTS (SELECT 1 FROM app.delivery_assignments a WHERE a.order_id = o.id
                             AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED'))
         ORDER BY o.accepted_at, o.id
    LOOP
        PERFORM set_config('app.reason', '', true);
        PERFORM app.offer_next(v_order);
    END LOOP;
    RETURN v_expired;
END $$;

-- Retention (DDR-43, DDR-113 (11)): delete GPS points received more than p_days ago (NULL = the
-- configured GPS_RETENTION_DAYS); audited; idempotent.
CREATE FUNCTION app.purge_delivery_locations(p_days integer) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, audit AS $$
DECLARE
    v_deleted integer;
BEGIN
    IF p_days IS NULL THEN
        SELECT c.value::integer INTO p_days FROM app.config_settings c
         WHERE c.key = 'GPS_RETENTION_DAYS' AND c.scope_type = 'GLOBAL';
    END IF;
    IF p_days IS NULL OR p_days < 1 THEN
        RAISE EXCEPTION 'retention days must be at least 1' USING ERRCODE = 'check_violation';
    END IF;
    DELETE FROM app.delivery_locations WHERE received_at < now() - make_interval(days => p_days);
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    INSERT INTO audit.events (actor_role, action, target_type, target_id, outcome, reason, after_summary)
    VALUES ('SYSTEM', 'delivery.locations.purged', 'delivery_locations', 'retention', 'SUCCESS',
            'GPS retention (DDR-43)', jsonb_build_object('deleted', v_deleted, 'days', p_days));
    RETURN v_deleted;
END $$;

REVOKE ALL ON FUNCTION app.offer_next(uuid), app.expire_and_reoffer(), app.purge_delivery_locations(integer)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.offer_next(uuid) TO app_api;
GRANT USAGE ON SCHEMA app TO worker;
GRANT EXECUTE ON FUNCTION app.expire_and_reoffer(), app.purge_delivery_locations(integer) TO worker;

-- ---------------------------------------------------------------- grants (app_api; fixture flags never writable)
GRANT SELECT, INSERT, UPDATE ON app.agent_availability TO app_api;
GRANT UPDATE (customer_unavailable_since) ON app.orders TO app_api;
GRANT SELECT ON app.delivery_otps, app.delivery_locations TO app_api;
GRANT INSERT (order_id, nonce, issued_by) ON app.delivery_otps TO app_api;
GRANT UPDATE (nonce, failed_attempts, issued_at, issued_by, verified_at) ON app.delivery_otps TO app_api;
GRANT INSERT (assignment_id, order_id, agent_user_id, location, accuracy_m, recorded_at, source)
    ON app.delivery_locations TO app_api;
"""

DOWNGRADE_SQL = """
REVOKE ALL ON app.agent_availability, app.delivery_otps, app.delivery_locations FROM app_api;
REVOKE UPDATE (customer_unavailable_since) ON app.orders FROM app_api;
DROP FUNCTION IF EXISTS app.purge_delivery_locations(integer);
DROP FUNCTION IF EXISTS app.expire_and_reoffer();
DROP FUNCTION IF EXISTS app.offer_next(uuid);
REVOKE USAGE ON SCHEMA app FROM worker;
DROP TABLE IF EXISTS app.delivery_locations;
DROP TABLE IF EXISTS app.delivery_otps;
DROP FUNCTION IF EXISTS app.inherit_order_flag_by_order_id();
ALTER TABLE app.orders DROP COLUMN IF EXISTS customer_unavailable_since;
DROP TABLE IF EXISTS app.agent_availability;
DELETE FROM app.config_settings WHERE key = 'GPS_STALE_SECONDS';
DELETE FROM app.status_transitions WHERE machine = 'assignment' AND from_status = 'FAILURE_REQUESTED'
    AND to_status = 'ACCEPTED';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
