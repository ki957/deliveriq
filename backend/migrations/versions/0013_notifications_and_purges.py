"""In-app notifications and retention purges (Task 11B; CU-25, DL-16, KI-23; DDR-115 (10)–(12)).

- `app.notifications`: one row per person and event, ids only (the UI words the kind; no names, phones,
  addresses or codes). Written by triggers, so every writer is covered (API, worker sweep, SQL functions):
  * customer, order lifecycle (CU-25): accepted, preparing, ready, out for delivery, delivered, cancelled,
    rejected, delivery failed, agent assigned;
  * agent (DL-16): new offer, offer withdrawn (reassignment or cancellation), failure request returned,
    failure approved. "Manager instructions" have no model in the sources and are not built;
  * Kitchen Manager (KI-23): an ingredient falls to or below its low-stock threshold.
  Each insert also sends a realtime notice (`notification`, user topic, DDR-115 (4)).
- Purges, daily by the worker through SECURITY DEFINER functions (the worker has no table grants,
  DDR-113 (17)), each audited with the count: notifications older than 30 days (DL-16; DDR-115 (11)); OTP
  challenges and sessions 30 days after they were used, expired or revoked (DDR-115 (12), closes DDR-107 (8)).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "order.accepted",
    "order.preparing",
    "order.ready_for_pickup",
    "order.out_for_delivery",
    "order.delivered",
    "order.cancelled",
    "order.rejected",
    "order.delivery_failed",
    "order.agent_assigned",
    "delivery.offered",
    "delivery.withdrawn",
    "delivery.failure_returned",
    "delivery.failure_approved",
    "stock.low",
)
_KINDS_SQL = ", ".join(f"'{k}'" for k in KINDS)

UPGRADE_SQL = f"""
CREATE TABLE app.notifications (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Derived rows: they go with their person, order, kitchen or ingredient.
    user_id          uuid NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    kind             text NOT NULL CHECK (kind IN ({_KINDS_SQL})),
    order_id         uuid REFERENCES app.orders (id) ON DELETE CASCADE,
    kitchen_id       uuid REFERENCES app.kitchens (id) ON DELETE CASCADE,
    ingredient_id    uuid REFERENCES app.ingredients (id) ON DELETE CASCADE,
    is_test_fixture  boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    read_at          timestamptz,
    CHECK ((kind = 'stock.low') = (ingredient_id IS NOT NULL AND kitchen_id IS NOT NULL)),
    CHECK ((kind = 'stock.low') OR order_id IS NOT NULL)
);
CREATE INDEX notifications_user_idx ON app.notifications (user_id, created_at DESC);
CREATE INDEX notifications_created_idx ON app.notifications (created_at);
GRANT SELECT ON app.notifications TO app_api;
GRANT UPDATE (read_at) ON app.notifications TO app_api;

-- ---------------------------------------------------------------- writers (SECURITY DEFINER triggers)
CREATE FUNCTION app.notify_order() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    IF NEW.fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP', 'OUT_FOR_DELIVERY', 'DELIVERED',
                                 'CANCELLED', 'REJECTED', 'DELIVERY_FAILED') THEN
        INSERT INTO app.notifications (user_id, kind, order_id, is_test_fixture)
        VALUES (NEW.customer_user_id, 'order.' || lower(NEW.fulfilment_status), NEW.id, NEW.is_test_fixture);
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION app.notify_assignment() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    o app.orders%ROWTYPE;
    k text;
BEGIN
    SELECT * INTO o FROM app.orders WHERE id = NEW.order_id;
    IF TG_OP = 'INSERT' THEN
        k := CASE WHEN NEW.status = 'OFFERED' THEN 'delivery.offered' END;
    ELSE
        k := CASE
            WHEN NEW.status = 'REVOKED' THEN 'delivery.withdrawn'
            WHEN OLD.status = 'FAILURE_REQUESTED' AND NEW.status = 'ACCEPTED' THEN 'delivery.failure_returned'
            WHEN NEW.status = 'FAILED' THEN 'delivery.failure_approved'
        END;
        -- The customer's "Agent Assigned" (DDR-16): only while the kitchen still holds the order.
        IF OLD.status = 'OFFERED' AND NEW.status = 'ACCEPTED'
           AND o.fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP') THEN
            INSERT INTO app.notifications (user_id, kind, order_id, is_test_fixture)
            VALUES (o.customer_user_id, 'order.agent_assigned', o.id, o.is_test_fixture);
        END IF;
    END IF;
    IF k IS NOT NULL THEN
        INSERT INTO app.notifications (user_id, kind, order_id, is_test_fixture)
        VALUES (NEW.agent_user_id, k, NEW.order_id, o.is_test_fixture);
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION app.notify_low_stock() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    -- Only when the available quantity crosses down to the threshold (KI-23), never on every update.
    IF NEW.low_stock_threshold IS NOT NULL
       AND NEW.on_hand - NEW.reserved <= NEW.low_stock_threshold
       AND (OLD.low_stock_threshold IS NULL OR OLD.on_hand - OLD.reserved > OLD.low_stock_threshold
            OR OLD.low_stock_threshold IS DISTINCT FROM NEW.low_stock_threshold) THEN
        INSERT INTO app.notifications (user_id, kind, kitchen_id, ingredient_id, is_test_fixture)
        SELECT DISTINCT ra.user_id, 'stock.low', NEW.kitchen_id, NEW.ingredient_id, NEW.is_test_fixture
          FROM app.role_assignments ra JOIN app.users u ON u.id = ra.user_id
         WHERE ra.role = 'KITCHEN_MANAGER' AND ra.kitchen_id = NEW.kitchen_id AND ra.revoked_at IS NULL
           AND u.status = 'ACTIVE';
    END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER y_notify_order AFTER UPDATE OF fulfilment_status ON app.orders
    FOR EACH ROW WHEN (OLD.fulfilment_status IS DISTINCT FROM NEW.fulfilment_status)
    EXECUTE FUNCTION app.notify_order();
CREATE TRIGGER y_notify_assignment_insert AFTER INSERT ON app.delivery_assignments
    FOR EACH ROW EXECUTE FUNCTION app.notify_assignment();
CREATE TRIGGER y_notify_assignment_update AFTER UPDATE OF status ON app.delivery_assignments
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status) EXECUTE FUNCTION app.notify_assignment();
CREATE TRIGGER y_notify_low_stock AFTER UPDATE ON app.ingredient_stock
    FOR EACH ROW EXECUTE FUNCTION app.notify_low_stock();

-- Realtime: a new notification reaches its owner's `me` topic (DDR-115 (4)).
CREATE OR REPLACE FUNCTION app.rt_notify_notification() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    PERFORM pg_notify('deliveriq_rt', jsonb_build_object('k', 'notification', 'id', NEW.id, 'u', NEW.user_id)::text);
    RETURN NULL;
END $$;
CREATE TRIGGER z_rt_notifications AFTER INSERT ON app.notifications
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify_notification();
REVOKE ALL ON FUNCTION app.notify_order(), app.notify_assignment(), app.notify_low_stock(),
    app.rt_notify_notification() FROM PUBLIC;

-- ---------------------------------------------------------------- purges (worker; audited; idempotent)
CREATE FUNCTION app.purge_notifications(p_days integer) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, audit AS $$
DECLARE
    v_deleted integer;
BEGIN
    IF p_days IS NULL OR p_days < 1 THEN
        RAISE EXCEPTION 'retention days must be at least 1' USING ERRCODE = 'check_violation';
    END IF;
    DELETE FROM app.notifications WHERE created_at < now() - make_interval(days => p_days);
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    INSERT INTO audit.events (actor_role, action, target_type, target_id, outcome, reason, after_summary)
    VALUES ('SYSTEM', 'notifications.purged', 'notifications', 'retention', 'SUCCESS',
            'Notification history (DL-16; DDR-115 (11))', jsonb_build_object('deleted', v_deleted, 'days', p_days));
    RETURN v_deleted;
END $$;

-- A session ends when it is revoked, reaches its absolute expiry or goes idle for 2 hours (DDR-98).
CREATE FUNCTION app.purge_auth(p_days integer) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, audit AS $$
DECLARE
    v_otps integer;
    v_sessions integer;
BEGIN
    IF p_days IS NULL OR p_days < 1 THEN
        RAISE EXCEPTION 'retention days must be at least 1' USING ERRCODE = 'check_violation';
    END IF;
    -- A challenge is used before it expires, so its expiry is its end.
    DELETE FROM app.otp_challenges WHERE expires_at < now() - make_interval(days => p_days);
    GET DIAGNOSTICS v_otps = ROW_COUNT;
    DELETE FROM app.sessions
     WHERE COALESCE(revoked_at, LEAST(expires_at, last_seen_at + interval '2 hours'))
           < now() - make_interval(days => p_days);
    GET DIAGNOSTICS v_sessions = ROW_COUNT;
    INSERT INTO audit.events (actor_role, action, target_type, target_id, outcome, reason, after_summary)
    VALUES ('SYSTEM', 'auth.records.purged', 'auth', 'retention', 'SUCCESS',
            'OTP challenge and session retention (DDR-115 (12))',
            jsonb_build_object('otp_challenges', v_otps, 'sessions', v_sessions, 'days', p_days));
    RETURN jsonb_build_object('otp_challenges', v_otps, 'sessions', v_sessions);
END $$;

REVOKE ALL ON FUNCTION app.purge_notifications(integer), app.purge_auth(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.purge_notifications(integer), app.purge_auth(integer) TO worker;
"""

DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS app.purge_auth(integer);
DROP FUNCTION IF EXISTS app.purge_notifications(integer);
DROP TRIGGER IF EXISTS z_rt_notifications ON app.notifications;
DROP TRIGGER IF EXISTS y_notify_low_stock ON app.ingredient_stock;
DROP TRIGGER IF EXISTS y_notify_assignment_update ON app.delivery_assignments;
DROP TRIGGER IF EXISTS y_notify_assignment_insert ON app.delivery_assignments;
DROP TRIGGER IF EXISTS y_notify_order ON app.orders;
DROP FUNCTION IF EXISTS app.rt_notify_notification();
DROP FUNCTION IF EXISTS app.notify_low_stock();
DROP FUNCTION IF EXISTS app.notify_assignment();
DROP FUNCTION IF EXISTS app.notify_order();
DROP TABLE IF EXISTS app.notifications;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
