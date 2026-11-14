"""Realtime change notices (Task 11A; PL-14, DDR-115 (2), (7), (13)).

Triggers on the tables the screens show call `pg_notify('deliveriq_rt', …)` with ids and scope only
(never names, phones, addresses, codes or amounts). NOTIFY is delivered on commit and from every writer:
the API, the worker and the SECURITY DEFINER job functions, so the outbox (analytics, Task 12) does not
need to cover screen updates. The API's listener relays each notice to Redis; the socket hub turns it
into `{topic, kind, id}` hints and the client refetches the REST view (DDR-115 (3), (4)).

Notice keys: `k` kind, `id`, `o` order, `c` customer, `a` agent, `ki` kitchen, `r` region, `st` order
status, `s` session, `u` user. The trigger function is SECURITY DEFINER so writers without table grants
(pipeline roles, the worker functions) can still resolve an order's scope.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNEL = "deliveriq_rt"

UPGRADE_SQL = f"""
-- The agent holding the order's live offer or delivery: order and item changes reach them too (pickup gate).
CREATE FUNCTION app.rt_live_agent(p_order uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, app AS $$
    SELECT agent_user_id FROM app.delivery_assignments
     WHERE order_id = p_order AND status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')
     ORDER BY created_at DESC LIMIT 1
$$;
REVOKE ALL ON FUNCTION app.rt_live_agent(uuid) FROM PUBLIC;

CREATE FUNCTION app.rt_notify() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, ops AS $$
DECLARE
    v jsonb;
    o app.orders%ROWTYPE;
BEGIN
    CASE TG_TABLE_NAME
    WHEN 'orders' THEN
        v := jsonb_build_object('k', 'order', 'id', NEW.id, 'o', NEW.id, 'c', NEW.customer_user_id,
                                'ki', NEW.kitchen_id, 'r', NEW.region_id, 'st', NEW.fulfilment_status,
                                'a', app.rt_live_agent(NEW.id));
    WHEN 'order_items', 'delivery_assignments', 'delivery_locations' THEN
        SELECT * INTO o FROM app.orders WHERE id = NEW.order_id;
        v := jsonb_build_object(
            'k', CASE TG_TABLE_NAME WHEN 'order_items' THEN 'order'
                                    WHEN 'delivery_assignments' THEN 'assignment' ELSE 'location' END,
            'id', NEW.order_id, 'o', NEW.order_id, 'c', o.customer_user_id, 'ki', o.kitchen_id,
            'r', o.region_id, 'st', o.fulfilment_status);
        v := v || jsonb_build_object('a', CASE TG_TABLE_NAME WHEN 'order_items' THEN app.rt_live_agent(NEW.order_id)
                                                ELSE (to_jsonb(NEW) ->> 'agent_user_id')::uuid END);
    WHEN 'kitchens' THEN
        v := jsonb_build_object('k', 'kitchen', 'id', NEW.id, 'ki', NEW.id, 'r', NEW.region_id);
    WHEN 'ingredient_stock', 'dish_availability_requests' THEN
        v := jsonb_build_object(
            'k', CASE TG_TABLE_NAME WHEN 'ingredient_stock' THEN 'stock' ELSE 'availability' END,
            'id', NEW.kitchen_id, 'ki', NEW.kitchen_id,
            'r', (SELECT region_id FROM app.kitchens WHERE id = NEW.kitchen_id));
    WHEN 'agent_availability' THEN
        v := jsonb_build_object('k', 'agent', 'id', NEW.agent_user_id, 'a', NEW.agent_user_id,
            'r', (SELECT region_id FROM app.role_assignments WHERE user_id = NEW.agent_user_id
                  AND role = 'DELIVERY_AGENT' AND revoked_at IS NULL ORDER BY granted_at LIMIT 1));
    WHEN 'pipeline_runs' THEN
        v := jsonb_build_object('k', 'run', 'id', NEW.id, 'r', NEW.region_id);
    WHEN 'pipeline_stage_runs' THEN
        v := jsonb_build_object('k', 'run', 'id', NEW.run_id,
            'r', (SELECT region_id FROM ops.pipeline_runs WHERE id = NEW.run_id));
    WHEN 'sessions' THEN
        v := jsonb_build_object('k', 'session', 's', NEW.id, 'u', NEW.user_id);
    WHEN 'users' THEN
        v := jsonb_build_object('k', 'user', 'u', NEW.id);
    END CASE;
    PERFORM pg_notify('{CHANNEL}', v::text);
    RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION app.rt_notify() FROM PUBLIC;

CREATE TRIGGER z_rt_orders AFTER INSERT OR UPDATE ON app.orders
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_order_items AFTER UPDATE OF prep_status ON app.order_items
    FOR EACH ROW WHEN (OLD.prep_status IS DISTINCT FROM NEW.prep_status) EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_delivery_assignments AFTER INSERT OR UPDATE ON app.delivery_assignments
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_delivery_locations AFTER INSERT ON app.delivery_locations
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_kitchens AFTER UPDATE ON app.kitchens
    FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_ingredient_stock AFTER INSERT OR UPDATE ON app.ingredient_stock
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_dish_availability AFTER INSERT OR UPDATE ON app.dish_availability_requests
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_agent_availability AFTER INSERT OR UPDATE ON app.agent_availability
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_pipeline_runs AFTER INSERT OR UPDATE ON ops.pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_pipeline_stage_runs AFTER INSERT OR UPDATE ON ops.pipeline_stage_runs
    FOR EACH ROW EXECUTE FUNCTION app.rt_notify();
-- Revocation stops events (DDR-115 (7)): a revoked session or a deactivated user closes its sockets.
CREATE TRIGGER z_rt_sessions AFTER UPDATE OF revoked_at ON app.sessions
    FOR EACH ROW WHEN (OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL)
    EXECUTE FUNCTION app.rt_notify();
CREATE TRIGGER z_rt_users AFTER UPDATE OF status ON app.users
    FOR EACH ROW WHEN (NEW.status <> 'ACTIVE' AND OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION app.rt_notify();
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS z_rt_users ON app.users;
DROP TRIGGER IF EXISTS z_rt_sessions ON app.sessions;
DROP TRIGGER IF EXISTS z_rt_pipeline_stage_runs ON ops.pipeline_stage_runs;
DROP TRIGGER IF EXISTS z_rt_pipeline_runs ON ops.pipeline_runs;
DROP TRIGGER IF EXISTS z_rt_agent_availability ON app.agent_availability;
DROP TRIGGER IF EXISTS z_rt_dish_availability ON app.dish_availability_requests;
DROP TRIGGER IF EXISTS z_rt_ingredient_stock ON app.ingredient_stock;
DROP TRIGGER IF EXISTS z_rt_kitchens ON app.kitchens;
DROP TRIGGER IF EXISTS z_rt_delivery_locations ON app.delivery_locations;
DROP TRIGGER IF EXISTS z_rt_delivery_assignments ON app.delivery_assignments;
DROP TRIGGER IF EXISTS z_rt_order_items ON app.order_items;
DROP TRIGGER IF EXISTS z_rt_orders ON app.orders;
DROP FUNCTION IF EXISTS app.rt_notify();
DROP FUNCTION IF EXISTS app.rt_live_agent(uuid);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
