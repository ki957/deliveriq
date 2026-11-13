"""Customer addresses, persisted cart, coupons and the checkout snapshot (Task 6A; DDR-110).

Sources: #1 §6 (multiple saved addresses, one default), §8 (one unified cart, persisted for
authenticated customers; 30-minute price protection; management-configured coupons), §9 (checkout
sequence), CU-02/03/11–17, DDR-53 (minimum before coupon), DDR-110 (price protection, coupon rules).

Coupons: migrations seed none. The only promotion in #15 §11 (POCWELCOME) is a DRAFT the owner has
not approved, so it is not loaded. A local/test fixture coupon is added by the fixture loader only.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
-- ---------------------------------------------------------------- price protection window (DDR-110)
INSERT INTO app.config_settings (key, value, unit, scope_type, is_test_default, source_ref)
VALUES ('PRICE_PROTECTION_MINUTES', 30, 'minutes', 'GLOBAL', false, '#1 §8; CU-13; DDR-110');

-- ---------------------------------------------------------------- bestseller flag (DDR-110: never set without approval)
ALTER TABLE app.menu_items ADD COLUMN is_bestseller boolean NOT NULL DEFAULT false;

-- ---------------------------------------------------------------- customer addresses (CU-02)
CREATE TABLE app.customer_addresses (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_user_id  uuid NOT NULL REFERENCES app.users (id),
    label             text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 40),
    address_line      text NOT NULL CHECK (char_length(address_line) BETWEEN 3 AND 300),
    location          geography(Point, 4326) NOT NULL,
    is_default        boolean NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    deleted_at        timestamptz
);
-- One default address per customer.
CREATE UNIQUE INDEX customer_addresses_one_default_uq ON app.customer_addresses (customer_user_id)
    WHERE is_default AND deleted_at IS NULL;
CREATE INDEX customer_addresses_customer_idx ON app.customer_addresses (customer_user_id) WHERE deleted_at IS NULL;
CREATE TRIGGER customer_addresses_touch BEFORE UPDATE ON app.customer_addresses
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

-- ---------------------------------------------------------------- persisted cart (CU-11, CU-13)
CREATE TABLE app.cart_items (
    customer_user_id  uuid NOT NULL REFERENCES app.users (id),
    menu_item_id      uuid NOT NULL REFERENCES app.menu_items (id),
    quantity          integer NOT NULL CHECK (quantity > 0),
    -- Price shown when the line was added; protected for PRICE_PROTECTION_MINUTES (DDR-110).
    unit_price_paise  integer NOT NULL CHECK (unit_price_paise > 0),
    added_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (customer_user_id, menu_item_id)
);

-- ---------------------------------------------------------------- coupons (CU-16, DDR-53, DDR-110)
CREATE TABLE app.coupons (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code                     text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9]{3,20}$'),
    discount_paise           integer NOT NULL CHECK (discount_paise > 0),
    min_food_subtotal_paise  integer NOT NULL DEFAULT 0 CHECK (min_food_subtotal_paise >= 0),
    usage_limit              integer CHECK (usage_limit > 0),
    used_count               integer NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    valid_from               timestamptz,
    valid_until              timestamptz,
    is_active                boolean NOT NULL DEFAULT false,
    is_test_fixture          boolean NOT NULL DEFAULT false,
    created_at               timestamptz NOT NULL DEFAULT now(),
    CHECK (usage_limit IS NULL OR used_count <= usage_limit),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from),
    -- DDR-48 naming rule, applied to coupon codes: fixture codes start with TEST.
    CONSTRAINT coupons_test_prefix CHECK (is_test_fixture = (code LIKE 'TEST%'))
);

-- ---------------------------------------------------------------- checkout snapshot on the order
ALTER TABLE app.orders
    ADD COLUMN discount_paise    integer NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
    ADD COLUMN coupon_id         uuid REFERENCES app.coupons (id),
    ADD COLUMN delivery_address  text,
    ADD COLUMN delivery_location geography(Point, 4326),
    ADD COLUMN straight_line_km  numeric(6, 2),
    ADD COLUMN road_km           numeric(6, 2),
    ADD COLUMN road_km_estimated boolean,
    DROP CONSTRAINT orders_payable_sum,
    -- A coupon may take the payable total below the ₹500 food minimum (DDR-53), never below zero.
    ADD CONSTRAINT orders_payable_sum CHECK (
        payable_paise IS NULL
        OR payable_paise = greatest(food_subtotal_paise + delivery_fee_paise - discount_paise, 0));

-- create_order (0008) gains the discount; same derivation of kitchen, region and fixture flag.
DROP FUNCTION app.create_order(uuid, uuid[], text, text, text, integer, integer);
CREATE FUNCTION app.create_order(
    p_customer              uuid,
    p_menu_items            uuid[],
    p_idempotency_key       text,
    p_request_hash          text,
    p_special_instructions  text,
    p_food_subtotal_paise   integer,
    p_delivery_fee_paise    integer,
    p_discount_paise        integer
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
                            delivery_fee_paise, discount_paise, payable_paise)
    VALUES (p_customer, v_kitchen, v_region, 'PLACED', p_special_instructions, v_fixture, p_idempotency_key,
            p_request_hash, p_food_subtotal_paise, p_delivery_fee_paise, p_discount_paise,
            greatest(p_food_subtotal_paise + p_delivery_fee_paise - p_discount_paise, 0))
    RETURNING id INTO v_id;
    RETURN v_id;
END $$;
REVOKE ALL ON FUNCTION app.create_order(uuid, uuid[], text, text, text, integer, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.create_order(uuid, uuid[], text, text, text, integer, integer, integer) TO app_api;

-- ---------------------------------------------------------------- grants (app_api)
GRANT SELECT, INSERT, UPDATE ON app.customer_addresses TO app_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.cart_items TO app_api;
GRANT SELECT ON app.coupons TO app_api;
GRANT UPDATE (used_count) ON app.coupons TO app_api;
GRANT UPDATE (coupon_id, delivery_address, delivery_location, straight_line_km, road_km, road_km_estimated)
    ON app.orders TO app_api;
"""

DOWNGRADE_SQL = """
REVOKE ALL ON app.customer_addresses, app.cart_items, app.coupons FROM app_api;
REVOKE UPDATE (coupon_id, delivery_address, delivery_location, straight_line_km, road_km, road_km_estimated)
    ON app.orders FROM app_api;
DROP FUNCTION IF EXISTS app.create_order(uuid, uuid[], text, text, text, integer, integer, integer);
CREATE FUNCTION app.create_order(
    p_customer uuid, p_menu_items uuid[], p_idempotency_key text, p_request_hash text,
    p_special_instructions text, p_food_subtotal_paise integer, p_delivery_fee_paise integer
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    v_kitchens integer; v_flags integer; v_found integer; v_kitchen uuid; v_region uuid;
    v_fixture boolean; v_id uuid;
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
ALTER TABLE app.orders
    DROP CONSTRAINT orders_payable_sum,
    DROP COLUMN road_km_estimated, DROP COLUMN road_km, DROP COLUMN straight_line_km,
    DROP COLUMN delivery_location, DROP COLUMN delivery_address, DROP COLUMN coupon_id,
    DROP COLUMN discount_paise,
    ADD CONSTRAINT orders_payable_sum CHECK (
        payable_paise IS NULL OR payable_paise = food_subtotal_paise + delivery_fee_paise);
DROP TABLE IF EXISTS app.coupons;
DROP TABLE IF EXISTS app.cart_items;
DROP TABLE IF EXISTS app.customer_addresses;
ALTER TABLE app.menu_items DROP COLUMN IF EXISTS is_bestseller;
DELETE FROM app.config_settings WHERE key = 'PRICE_PROTECTION_MINUTES';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
