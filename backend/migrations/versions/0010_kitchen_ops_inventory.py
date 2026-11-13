"""Kitchen operations and inventory (Task 8A; DDR-10, DDR-37, DDR-42, DDR-51, DDR-111).

Sources: #4 §3 (modes, capacity of accepted non-terminal orders), §4–§6 (acceptance, FIFO by
acceptance time, item preparation), §7 (ingredient stock: reserve on acceptance, deduct on handover,
release on cancel/reject, atomic, adjustments need a reason and an audit record), §7.3 (dish
unavailability requested by the kitchen, approved by the RM), §8 (cannot fulfil an accepted order),
KI-01–KI-24, DDR-111.

- `orders.accepted_at` drives the FIFO queue (KI-03); warnings never reorder it.
- New fulfilment transitions ACCEPTED/PREPARING/READY_FOR_PICKUP → REJECTED for "cannot fulfil"
  (KM, RM, CA only; reason required; DDR-111 (5)).
- Kitchen test defaults (DDR-42 stays open): Busy capacity 5 and acceptance timeout 5 minutes,
  labelled `is_test_default` like MAX_CONCURRENT_ORDERS.
- Stock per kitchen and ingredient, reservations per order and ingredient, and an append-only stock
  ledger. Fixture flags are never written by the API: each row derives its flag from its parent, and
  TEST and real rows never mix (DDR-37, DDR-48, DDR-74).
- One open offer or live delivery per agent (DDR-111 (6)).
- Dish availability requests with one pending request per dish (DDR-111 (7)).

Migrations seed no stock: the TEST opening stock is loaded by the fixture loader only (DDR-111 (8)).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
-- ---------------------------------------------------------------- FIFO by acceptance time (KI-03)
ALTER TABLE app.orders ADD COLUMN accepted_at timestamptz;
CREATE INDEX orders_kitchen_fifo_idx ON app.orders (kitchen_id, accepted_at, id)
    WHERE fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP');

-- ---------------------------------------------------------------- "cannot fulfil" after acceptance (DDR-111 (5))
INSERT INTO app.status_transitions (machine, from_status, to_status, reason_required, allowed_roles, source_ref)
VALUES
    ('fulfilment', 'ACCEPTED', 'REJECTED', true,
     ARRAY['KITCHEN_MANAGER', 'REGIONAL_MANAGER', 'CENTRAL_ADMIN'], 'KI-11; #4 §8; DDR-111 (5)'),
    ('fulfilment', 'PREPARING', 'REJECTED', true,
     ARRAY['KITCHEN_MANAGER', 'REGIONAL_MANAGER', 'CENTRAL_ADMIN'], 'KI-11; #4 §8; DDR-111 (5)'),
    ('fulfilment', 'READY_FOR_PICKUP', 'REJECTED', true,
     ARRAY['KITCHEN_MANAGER', 'REGIONAL_MANAGER', 'CENTRAL_ADMIN'], 'KI-11; #4 §8; DDR-111 (5)');

-- ---------------------------------------------------------------- kitchen test defaults (DDR-42 open; DDR-111 (1))
INSERT INTO app.config_settings (key, value, unit, scope_type, region_id, kitchen_id, is_test_default, source_ref)
SELECT 'MAX_CONCURRENT_ORDERS_BUSY', 5, 'orders', 'KITCHEN', NULL, k.id, true,
       '#4 §3 "lower configured capacity"; DDR-42 open; DDR-111 (1) test default'
  FROM app.kitchens k WHERE k.code = 'KIT-CHN-001';
INSERT INTO app.config_settings (key, value, unit, scope_type, region_id, kitchen_id, is_test_default, source_ref)
SELECT 'KITCHEN_ACCEPTANCE_TIMEOUT', 5, 'minutes', 'KITCHEN', NULL, k.id, true,
       '#14 §3.2 test default; #4 §4 KI-02; DDR-42 open; DDR-111 (1)'
  FROM app.kitchens k WHERE k.code = 'KIT-CHN-001';

-- ---------------------------------------------------------------- stock per kitchen and ingredient (KI-21)
CREATE TABLE app.ingredient_stock (
    kitchen_id           uuid NOT NULL REFERENCES app.kitchens (id),
    ingredient_id        uuid NOT NULL REFERENCES app.ingredients (id),
    -- Quantities in the ingredient's own unit (g, ml or piece); no purchase-unit conversion (DDR-111 (8)).
    on_hand              numeric(14, 3) NOT NULL CHECK (on_hand >= 0),
    reserved             numeric(14, 3) NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    -- Unset by default; the Kitchen Manager sets it (DDR-42 open; DDR-111 (1)).
    low_stock_threshold  numeric(14, 3) CHECK (low_stock_threshold >= 0),
    -- Derived from the ingredient's origin; DDR-37 opening stock is test-only.
    is_test_fixture      boolean NOT NULL DEFAULT false,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kitchen_id, ingredient_id),
    UNIQUE (kitchen_id, ingredient_id, is_test_fixture),
    -- Reservations can never exceed what is on hand: no oversell even if a caller skips the check.
    CONSTRAINT ingredient_stock_reserved_le_on_hand CHECK (reserved <= on_hand)
);
CREATE TRIGGER ingredient_stock_touch BEFORE UPDATE ON app.ingredient_stock
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

CREATE FUNCTION app.derive_stock_fixture_flag() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    SELECT i.origin = 'TEST_FIXTURE' INTO NEW.is_test_fixture FROM app.ingredients i WHERE i.id = NEW.ingredient_id;
    RETURN NEW;
END $$;
CREATE TRIGGER a_ingredient_stock_fixture BEFORE INSERT ON app.ingredient_stock
    FOR EACH ROW EXECUTE FUNCTION app.derive_stock_fixture_flag();
-- The flag never changes after insert.
CREATE FUNCTION app.keep_fixture_flag() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, app AS $$
BEGIN
    IF NEW.is_test_fixture IS DISTINCT FROM OLD.is_test_fixture THEN
        RAISE EXCEPTION 'is_test_fixture cannot change' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER b_ingredient_stock_keep_flag BEFORE UPDATE ON app.ingredient_stock
    FOR EACH ROW EXECUTE FUNCTION app.keep_fixture_flag();

-- ---------------------------------------------------------------- reservations per order (KI-22)
CREATE TABLE app.stock_reservations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id         uuid NOT NULL,
    kitchen_id       uuid NOT NULL,
    ingredient_id    uuid NOT NULL,
    quantity         numeric(14, 3) NOT NULL CHECK (quantity > 0),
    -- RESERVED at acceptance; CONSUMED at handover (once); RELEASED on reject.
    status           text NOT NULL CHECK (status IN ('RESERVED', 'CONSUMED', 'RELEASED')),
    is_test_fixture  boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (order_id, ingredient_id),
    -- Test and real data never mix: the order and the stock row carry the same flag.
    FOREIGN KEY (order_id, is_test_fixture) REFERENCES app.orders (id, is_test_fixture),
    FOREIGN KEY (kitchen_id, ingredient_id, is_test_fixture)
        REFERENCES app.ingredient_stock (kitchen_id, ingredient_id, is_test_fixture)
);
CREATE INDEX stock_reservations_order_idx ON app.stock_reservations (order_id);
CREATE TRIGGER stock_reservations_touch BEFORE UPDATE ON app.stock_reservations
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

CREATE FUNCTION app.inherit_reservation_fixture_flag() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    SELECT o.is_test_fixture INTO NEW.is_test_fixture FROM app.orders o WHERE o.id = NEW.order_id;
    RETURN NEW;
END $$;
CREATE TRIGGER a_stock_reservations_fixture BEFORE INSERT ON app.stock_reservations
    FOR EACH ROW EXECUTE FUNCTION app.inherit_reservation_fixture_flag();
CREATE TRIGGER b_stock_reservations_keep_flag BEFORE UPDATE ON app.stock_reservations
    FOR EACH ROW EXECUTE FUNCTION app.keep_fixture_flag();
-- A reservation only moves forward, once: RESERVED → CONSUMED or RESERVED → RELEASED.
CREATE FUNCTION app.check_reservation_step() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, app AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status AND OLD.status <> 'RESERVED' THEN
        RAISE EXCEPTION 'reservation is already %', OLD.status USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.quantity IS DISTINCT FROM OLD.quantity OR NEW.order_id IS DISTINCT FROM OLD.order_id
       OR NEW.ingredient_id IS DISTINCT FROM OLD.ingredient_id THEN
        RAISE EXCEPTION 'reservation lines are immutable' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER c_stock_reservations_step BEFORE UPDATE ON app.stock_reservations
    FOR EACH ROW EXECUTE FUNCTION app.check_reservation_step();

-- ---------------------------------------------------------------- append-only stock ledger (#4 §7.2)
CREATE TABLE app.stock_movements (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kitchen_id       uuid NOT NULL,
    ingredient_id    uuid NOT NULL,
    delta            numeric(14, 3) NOT NULL CHECK (delta <> 0),
    kind             text NOT NULL CHECK (kind IN ('OPENING', 'ADJUSTMENT', 'CONSUMPTION')),
    order_id         uuid REFERENCES app.orders (id),
    reason           text CHECK (char_length(reason) <= 500),
    -- Like app.status_history: the actor id is kept as history, without a foreign key.
    actor_user_id    uuid,
    actor_role       text NOT NULL,
    is_test_fixture  boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (kitchen_id, ingredient_id, is_test_fixture)
        REFERENCES app.ingredient_stock (kitchen_id, ingredient_id, is_test_fixture),
    CONSTRAINT stock_movements_consumption_has_order CHECK ((kind = 'CONSUMPTION') = (order_id IS NOT NULL)),
    CONSTRAINT stock_movements_adjustment_has_reason CHECK (kind <> 'ADJUSTMENT' OR char_length(reason) > 0),
    CONSTRAINT stock_movements_actor CHECK (actor_role = 'SYSTEM' OR actor_user_id IS NOT NULL)
);
-- Duplicate handover deducts once (KI-22): one consumption per order and ingredient.
CREATE UNIQUE INDEX stock_movements_one_consumption_uq ON app.stock_movements (order_id, ingredient_id)
    WHERE kind = 'CONSUMPTION';
CREATE INDEX stock_movements_stock_idx ON app.stock_movements (kitchen_id, ingredient_id, created_at DESC);

CREATE FUNCTION app.inherit_movement_fixture_flag() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    SELECT s.is_test_fixture INTO NEW.is_test_fixture FROM app.ingredient_stock s
     WHERE s.kitchen_id = NEW.kitchen_id AND s.ingredient_id = NEW.ingredient_id;
    RETURN NEW;
END $$;
CREATE TRIGGER a_stock_movements_fixture BEFORE INSERT ON app.stock_movements
    FOR EACH ROW EXECUTE FUNCTION app.inherit_movement_fixture_flag();
CREATE TRIGGER stock_movements_append_only BEFORE UPDATE OR DELETE ON app.stock_movements
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();

-- ---------------------------------------------------------------- one open offer or live delivery per agent (DDR-111 (6))
CREATE UNIQUE INDEX delivery_assignments_one_live_per_agent_uq ON app.delivery_assignments (agent_user_id)
    WHERE status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED');

-- ---------------------------------------------------------------- dish availability requests (KI-24; DDR-111 (7))
CREATE TABLE app.dish_availability_requests (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    menu_item_id     uuid NOT NULL REFERENCES app.menu_items (id),
    kitchen_id       uuid NOT NULL REFERENCES app.kitchens (id),
    region_id        uuid NOT NULL REFERENCES app.regions (id),
    kind             text NOT NULL CHECK (kind IN ('MAKE_UNAVAILABLE', 'MAKE_AVAILABLE')),
    reason           text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
    status           text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    requested_by     uuid NOT NULL REFERENCES app.users (id),
    requested_role   text NOT NULL,
    requested_at     timestamptz NOT NULL DEFAULT now(),
    decided_by       uuid REFERENCES app.users (id),
    decided_role     text,
    decided_at       timestamptz,
    decision_reason  text CHECK (char_length(decision_reason) <= 500),
    -- Derived from the dish: requests about TEST dishes are fixture rows (DDR-74; leak control 3).
    is_test_fixture  boolean NOT NULL DEFAULT false,
    FOREIGN KEY (menu_item_id, is_test_fixture) REFERENCES app.menu_items (id, is_test_fixture),
    CONSTRAINT dish_availability_decision_complete CHECK (
        (status = 'PENDING') = (decided_by IS NULL AND decided_at IS NULL AND decided_role IS NULL)),
    CONSTRAINT dish_availability_rejection_reason CHECK (
        status <> 'REJECTED' OR char_length(decision_reason) > 0)
);
CREATE UNIQUE INDEX dish_availability_one_pending_uq ON app.dish_availability_requests (menu_item_id)
    WHERE status = 'PENDING';
CREATE INDEX dish_availability_region_idx ON app.dish_availability_requests (region_id, status, requested_at);
CREATE FUNCTION app.inherit_availability_fixture_flag() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    SELECT m.is_test_fixture INTO NEW.is_test_fixture FROM app.menu_items m WHERE m.id = NEW.menu_item_id;
    RETURN NEW;
END $$;
CREATE TRIGGER a_dish_availability_fixture BEFORE INSERT ON app.dish_availability_requests
    FOR EACH ROW EXECUTE FUNCTION app.inherit_availability_fixture_flag();
CREATE TRIGGER b_dish_availability_keep_flag BEFORE UPDATE ON app.dish_availability_requests
    FOR EACH ROW EXECUTE FUNCTION app.keep_fixture_flag();

-- ---------------------------------------------------------------- grants (app_api; fixture flags never writable)
GRANT UPDATE (accepted_at) ON app.orders TO app_api;
GRANT SELECT ON app.ingredient_stock, app.stock_reservations, app.stock_movements,
    app.dish_availability_requests TO app_api;
GRANT UPDATE (on_hand, reserved, low_stock_threshold) ON app.ingredient_stock TO app_api;
GRANT INSERT (order_id, kitchen_id, ingredient_id, quantity, status) ON app.stock_reservations TO app_api;
GRANT UPDATE (status) ON app.stock_reservations TO app_api;
GRANT INSERT (kitchen_id, ingredient_id, delta, kind, order_id, reason, actor_user_id, actor_role)
    ON app.stock_movements TO app_api;
GRANT INSERT (menu_item_id, kitchen_id, region_id, kind, reason, requested_by, requested_role)
    ON app.dish_availability_requests TO app_api;
GRANT UPDATE (status, decided_by, decided_role, decided_at, decision_reason)
    ON app.dish_availability_requests TO app_api;
"""

DOWNGRADE_SQL = """
REVOKE ALL ON app.ingredient_stock, app.stock_reservations, app.stock_movements,
    app.dish_availability_requests FROM app_api;
REVOKE UPDATE (accepted_at) ON app.orders FROM app_api;
DROP TABLE IF EXISTS app.dish_availability_requests;
DROP FUNCTION IF EXISTS app.inherit_availability_fixture_flag();
DROP INDEX IF EXISTS app.delivery_assignments_one_live_per_agent_uq;
DROP TABLE IF EXISTS app.stock_movements;
DROP TABLE IF EXISTS app.stock_reservations;
DROP TABLE IF EXISTS app.ingredient_stock;
DROP FUNCTION IF EXISTS app.inherit_movement_fixture_flag();
DROP FUNCTION IF EXISTS app.check_reservation_step();
DROP FUNCTION IF EXISTS app.inherit_reservation_fixture_flag();
DROP FUNCTION IF EXISTS app.keep_fixture_flag();
DROP FUNCTION IF EXISTS app.derive_stock_fixture_flag();
DELETE FROM app.config_settings WHERE key IN ('MAX_CONCURRENT_ORDERS_BUSY', 'KITCHEN_ACCEPTANCE_TIMEOUT');
DELETE FROM app.status_transitions WHERE machine = 'fulfilment' AND to_status = 'REJECTED'
    AND from_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP');
DROP INDEX IF EXISTS app.orders_kitchen_fifo_idx;
ALTER TABLE app.orders DROP COLUMN IF EXISTS accepted_at;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
