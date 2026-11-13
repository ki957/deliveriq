"""Order placement, price snapshots, checkout idempotency and simulated payment amounts.

Sources: Phase 2 §6 ("order and item snapshots at placement", "idempotency keys for checkout and
payment simulation"), DDR-38 (₹30 fee), DDR-109 (fixture flag derived from the chosen dishes,
idempotency, routine refund). Money is integer paise (Task 3).

An order's `is_test_fixture` flag is never sent by the API: `app.create_order()` derives it from the
chosen dishes (all TEST or all real, never mixed), and order items and payments inherit it from their
order. The leak controls of plan §5.2 still hold: fixture dishes exist only in local/test databases
and the production startup check refuses any fixture row.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
-- ---------------------------------------------------------------- snapshots and idempotency
ALTER TABLE app.orders
    ADD COLUMN idempotency_key      text,
    ADD COLUMN request_hash         char(64),
    ADD COLUMN food_subtotal_paise  integer CHECK (food_subtotal_paise >= 0),
    ADD COLUMN delivery_fee_paise   integer CHECK (delivery_fee_paise >= 0),
    ADD COLUMN payable_paise        integer CHECK (payable_paise >= 0),
    ADD CONSTRAINT orders_payable_sum CHECK (
        payable_paise IS NULL OR payable_paise = food_subtotal_paise + delivery_fee_paise);
-- DDR-109: one order per customer and idempotency key, kept with the order.
CREATE UNIQUE INDEX orders_customer_idempotency_uq ON app.orders (customer_user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

ALTER TABLE app.order_items
    ADD COLUMN item_name         text,
    ADD COLUMN unit_price_paise  integer CHECK (unit_price_paise > 0);

ALTER TABLE app.payments
    ADD COLUMN amount_paise   integer CHECK (amount_paise >= 0),
    -- Simulated transaction reference: never a real gateway ID (#7 §8, Phase 4 §13).
    ADD COLUMN sim_reference  text CHECK (sim_reference ~ '^SIM-[0-9A-F]{12}$');
-- DDR-109: one payment per order.
CREATE UNIQUE INDEX payments_one_per_order_uq ON app.payments (order_id);

-- ---------------------------------------------------------------- controlled order creation (DDR-109)
CREATE FUNCTION app.create_order(
    p_customer              uuid,
    p_menu_items            uuid[],
    p_idempotency_key       text,
    p_request_hash          text,
    p_special_instructions  text,
    p_food_subtotal_paise   integer,
    p_delivery_fee_paise    integer
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    v_kitchens  integer;
    v_flags     integer;
    v_found     integer;
    v_kitchen   uuid;
    v_region    uuid;
    v_fixture   boolean;
    v_id        uuid;
BEGIN
    IF p_menu_items IS NULL OR cardinality(p_menu_items) = 0 THEN
        RAISE EXCEPTION 'an order needs at least one dish' USING ERRCODE = 'check_violation';
    END IF;
    SELECT count(DISTINCT m.id), count(DISTINCT m.kitchen_id), count(DISTINCT m.is_test_fixture),
           min(m.kitchen_id::text)::uuid, bool_and(m.is_test_fixture)
      INTO v_found, v_kitchens, v_flags, v_kitchen, v_fixture
      FROM app.menu_items m WHERE m.id = ANY (p_menu_items);
    IF v_found <> (SELECT count(DISTINCT x) FROM unnest(p_menu_items) AS x) THEN
        RAISE EXCEPTION 'unknown dish in order' USING ERRCODE = 'check_violation';
    END IF;
    IF v_kitchens <> 1 THEN
        RAISE EXCEPTION 'all dishes in an order must come from one kitchen' USING ERRCODE = 'check_violation';
    END IF;
    IF v_flags <> 1 THEN
        RAISE EXCEPTION 'an order cannot mix TEST and real dishes' USING ERRCODE = 'check_violation';
    END IF;
    SELECT k.region_id INTO v_region FROM app.kitchens k WHERE k.id = v_kitchen;
    INSERT INTO app.orders (customer_user_id, kitchen_id, region_id, fulfilment_status, special_instructions,
                            is_test_fixture, idempotency_key, request_hash, food_subtotal_paise,
                            delivery_fee_paise, payable_paise)
    VALUES (p_customer, v_kitchen, v_region, 'PLACED', p_special_instructions, v_fixture, p_idempotency_key,
            p_request_hash, p_food_subtotal_paise, p_delivery_fee_paise,
            p_food_subtotal_paise + p_delivery_fee_paise)
    RETURNING id INTO v_id;
    RETURN v_id;
END $$;
REVOKE ALL ON FUNCTION app.create_order(uuid, uuid[], text, text, text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.create_order(uuid, uuid[], text, text, text, integer, integer) TO app_api;

-- Order items and payments always carry their order's flag, whatever the caller sends (DDR-109).
CREATE FUNCTION app.inherit_order_fixture_flag() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    SELECT o.is_test_fixture INTO NEW.is_test_fixture FROM app.orders o WHERE o.id = NEW.order_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'order % does not exist', NEW.order_id USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER a0_order_items_fixture_flag BEFORE INSERT ON app.order_items
    FOR EACH ROW EXECUTE FUNCTION app.inherit_order_fixture_flag();
CREATE TRIGGER a0_payments_fixture_flag BEFORE INSERT ON app.payments
    FOR EACH ROW EXECUTE FUNCTION app.inherit_order_fixture_flag();

-- ---------------------------------------------------------------- grants for the new columns
GRANT INSERT (item_name, unit_price_paise) ON app.order_items TO app_api;
GRANT INSERT (amount_paise, sim_reference) ON app.payments TO app_api;
"""

DOWNGRADE_SQL = """
REVOKE INSERT (amount_paise, sim_reference) ON app.payments FROM app_api;
REVOKE INSERT (item_name, unit_price_paise) ON app.order_items FROM app_api;
DROP TRIGGER IF EXISTS a0_payments_fixture_flag ON app.payments;
DROP TRIGGER IF EXISTS a0_order_items_fixture_flag ON app.order_items;
DROP FUNCTION IF EXISTS app.inherit_order_fixture_flag();
DROP FUNCTION IF EXISTS app.create_order(uuid, uuid[], text, text, text, integer, integer);
DROP INDEX IF EXISTS app.payments_one_per_order_uq;
ALTER TABLE app.payments DROP COLUMN IF EXISTS sim_reference, DROP COLUMN IF EXISTS amount_paise;
ALTER TABLE app.order_items DROP COLUMN IF EXISTS unit_price_paise, DROP COLUMN IF EXISTS item_name;
DROP INDEX IF EXISTS app.orders_customer_idempotency_uq;
ALTER TABLE app.orders
    DROP CONSTRAINT IF EXISTS orders_payable_sum,
    DROP COLUMN IF EXISTS payable_paise, DROP COLUMN IF EXISTS delivery_fee_paise,
    DROP COLUMN IF EXISTS food_subtotal_paise, DROP COLUMN IF EXISTS request_hash,
    DROP COLUMN IF EXISTS idempotency_key;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
