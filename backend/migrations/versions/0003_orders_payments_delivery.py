"""Orders, order items, payments and delivery assignments with their canonical status machines,
plus the transition data for all six machines.

Only the columns needed for the state machines, fixture controls and Task 3 acceptance are created
here. Money snapshots and checkout fields (Tasks 6-7), stock (Task 8) and GPS (Task 9) are added by
the tasks that own them.

Sources: Matrix §7 (DDR-17), DDR-16, DDR-10/11, CU-09/DDR-07 (250 chars), CU-19, DL-03/04, DA-18,
#15 §9 (payment methods), DDR-48 (fixture flags).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FULFILMENT = (
    "PLACED",
    "PENDING_KITCHEN",
    "ACCEPTED",
    "PREPARING",
    "READY_FOR_PICKUP",
    "PICKED_UP",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "CANCELLED",
    "REJECTED",
    "DELIVERY_FAILED",
)
PAYMENT = (
    "PENDING",
    "SUCCEEDED",
    "FAILED",
    "TIMED_OUT",
    "REFUND_PENDING",
    "REFUNDED",
    "COLLECTION_PENDING",
    "COLLECTED",
    "MISMATCH",
)
ASSIGNMENT = (
    "OFFERED",
    "ACCEPTED",
    "REJECTED",
    "EXPIRED",
    "REVOKED",
    "COMPLETED",
    "FAILURE_REQUESTED",
    "FAILED",
)
ITEM = ("PENDING", "PREPARING", "PREPARED")

# (machine, from, to, reason_required, allowed_roles, source)
# allowed_roles only where a DDR names the authority; everything else is checked by services.
TRANSITIONS: tuple[tuple[str, str, str, bool, tuple[str, ...] | None, str], ...] = (
    ("fulfilment", "PLACED", "PENDING_KITCHEN", False, None, "Matrix §7.1; CU-18"),
    ("fulfilment", "PLACED", "CANCELLED", False, None, "Matrix §7.1 (prepaid failure / customer cancel)"),
    ("fulfilment", "PENDING_KITCHEN", "ACCEPTED", False, None, "Matrix §7.1; #4 §4"),
    ("fulfilment", "PENDING_KITCHEN", "REJECTED", True, None, "Matrix §7.1; #4 §2.2 reject needs reason"),
    ("fulfilment", "PENDING_KITCHEN", "CANCELLED", False, None, "CU-19 cancel before acceptance"),
    ("fulfilment", "ACCEPTED", "PREPARING", False, None, "Matrix §7.1; KI-04"),
    ("fulfilment", "PREPARING", "READY_FOR_PICKUP", False, None, "Matrix §7.1; KI-05"),
    ("fulfilment", "READY_FOR_PICKUP", "PICKED_UP", False, None, "Matrix §7.1; KI-08; DL-09"),
    ("fulfilment", "PICKED_UP", "OUT_FOR_DELIVERY", False, None, "DDR-16 automatic, same transaction"),
    ("fulfilment", "OUT_FOR_DELIVERY", "DELIVERED", False, None, "Matrix §7.1; DA-16 OTP"),
    ("fulfilment", "OUT_FOR_DELIVERY", "DELIVERY_FAILED", True, None, "Matrix §7.1; DA-18"),
    ("payment", "PENDING", "SUCCEEDED", False, None, "Matrix §7.2; #15 §9"),
    ("payment", "PENDING", "FAILED", False, None, "Matrix §7.2; #15 §9"),
    ("payment", "PENDING", "TIMED_OUT", False, None, "Matrix §7.2; #15 §9"),
    ("payment", "SUCCEEDED", "REFUND_PENDING", True, None, "Matrix §7.2; CU-19; MG-05"),
    ("payment", "REFUND_PENDING", "REFUNDED", False, None, "Matrix §7.2"),
    ("payment", "COLLECTION_PENDING", "COLLECTED", False, None, "Matrix §7.2; #15 §9"),
    (
        "payment",
        "COLLECTION_PENDING",
        "MISMATCH",
        True,
        None,
        "Matrix §7.2; #7 'Handle COD mismatch escalations'",
    ),
    ("assignment", "OFFERED", "ACCEPTED", False, None, "Matrix §7.2; #7 §3"),
    ("assignment", "OFFERED", "REJECTED", True, None, "DL-04 rejection requires reason"),
    ("assignment", "OFFERED", "EXPIRED", False, None, "DL-04 60-second timeout"),
    ("assignment", "OFFERED", "REVOKED", False, None, "DL-02 manager override"),
    ("assignment", "ACCEPTED", "REVOKED", True, None, "DL-07 reassignment revokes access"),
    ("assignment", "ACCEPTED", "COMPLETED", False, None, "Matrix §7.2"),
    ("assignment", "ACCEPTED", "FAILURE_REQUESTED", True, None, "DA-18 agent reason"),
    ("assignment", "FAILURE_REQUESTED", "FAILED", False, None, "DA-18 manager approves"),
    ("item", "PENDING", "PREPARING", False, None, "KI-05"),
    ("item", "PREPARING", "PREPARED", False, None, "KI-05"),
    ("recipe", "DRAFT", "PENDING_VALIDATION", True, None, "DDR-10 submit"),
    ("recipe", "PENDING_VALIDATION", "DRAFT", True, None, "DDR-10 return"),
    ("recipe", "PENDING_VALIDATION", "VALIDATED", True, None, "DDR-10 validate"),
    ("recipe", "VALIDATED", "ACTIVE", True, ("KITCHEN_MANAGER",), "DDR-10/DDR-30 KM activates"),
    ("recipe", "VALIDATED", "REJECTED", True, None, "DDR-10 reject"),
    ("recipe", "ACTIVE", "SUPERSEDED", True, None, "DDR-10 new version supersedes"),
    ("recipe", "ACTIVE", "DISABLED", True, None, "DDR-10"),
    ("menu", "DRAFT", "READY_FOR_PUBLICATION", False, None, "DDR-11"),
    (
        "menu",
        "READY_FOR_PUBLICATION",
        "PUBLISHED",
        False,
        ("REGIONAL_MANAGER", "CENTRAL_ADMIN"),
        "DDR-11/DDR-31",
    ),
    (
        "menu",
        "PUBLISHED",
        "TEMPORARILY_UNAVAILABLE",
        True,
        ("REGIONAL_MANAGER", "CENTRAL_ADMIN"),
        "DDR-11; KI-24",
    ),
    ("menu", "TEMPORARILY_UNAVAILABLE", "PUBLISHED", False, ("REGIONAL_MANAGER", "CENTRAL_ADMIN"), "DDR-11"),
    ("menu", "PUBLISHED", "RETIRED", True, ("REGIONAL_MANAGER", "CENTRAL_ADMIN"), "DDR-11"),
)

INITIAL: tuple[tuple[str, str, str], ...] = (
    ("fulfilment", "PLACED", "Matrix §7.1"),
    ("payment", "PENDING", "Matrix §7.2 prepaid"),
    ("payment", "COLLECTION_PENDING", "Matrix §7.2 COD"),
    ("assignment", "OFFERED", "#7 §3"),
    ("item", "PENDING", "KI-05"),
    ("recipe", "DRAFT", "DDR-09"),
    ("recipe", "QUARANTINED_DUPLICATE_CANDIDATE", "DDR-13"),
    ("menu", "DRAFT", "DDR-11"),
)


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _roles(roles: tuple[str, ...] | None) -> str:
    return "NULL" if roles is None else "ARRAY[" + ", ".join(_literal(r) for r in roles) + "]"


TRANSITION_ROWS = ",\n".join(
    f"({_literal(m)}, {_literal(a)}, {_literal(b)}, {str(r).lower()}, {_roles(roles)}, {_literal(src)})"
    for m, a, b, r, roles, src in TRANSITIONS
)
INITIAL_ROWS = ",\n".join(f"({_literal(m)}, {_literal(s)}, {_literal(src)})" for m, s, src in INITIAL)

UPGRADE_SQL = f"""
INSERT INTO app.status_transitions (machine, from_status, to_status, reason_required, allowed_roles, source_ref)
VALUES {TRANSITION_ROWS};

INSERT INTO app.status_initial (machine, status, source_ref) VALUES {INITIAL_ROWS};

-- ---------------------------------------------------------------- orders
CREATE TABLE app.orders (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_user_id         uuid NOT NULL REFERENCES app.users (id),
    kitchen_id               uuid NOT NULL,
    region_id                uuid NOT NULL,
    fulfilment_status        text NOT NULL CHECK (fulfilment_status IN ({_in(FULFILMENT)})),
    -- Flag, not a status, so the main status never regresses (Matrix §7.1).
    delivery_exception_open  boolean NOT NULL DEFAULT false,
    special_instructions     text CHECK (char_length(special_instructions) <= 250),
    is_test_fixture          boolean NOT NULL DEFAULT false,
    version                  integer NOT NULL DEFAULT 1,
    placed_at                timestamptz NOT NULL DEFAULT now(),
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, is_test_fixture),
    -- The order's region is always its kitchen's region.
    FOREIGN KEY (kitchen_id, region_id) REFERENCES app.kitchens (id, region_id)
);
CREATE INDEX orders_kitchen_status_idx ON app.orders (kitchen_id, fulfilment_status);
CREATE INDEX orders_customer_idx ON app.orders (customer_user_id, placed_at DESC);

CREATE TABLE app.order_items (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           uuid NOT NULL,
    menu_item_id       uuid NOT NULL,
    -- Pinned at kitchen acceptance (KI-18); NULL until then.
    recipe_version_id  uuid REFERENCES app.recipe_versions (id),
    quantity           integer NOT NULL CHECK (quantity > 0),
    prep_status        text NOT NULL CHECK (prep_status IN ({_in(ITEM)})),
    is_test_fixture    boolean NOT NULL DEFAULT false,
    created_at         timestamptz NOT NULL DEFAULT now(),
    -- Fixture flags must match their order and menu item: test and real data never mix.
    FOREIGN KEY (order_id, is_test_fixture) REFERENCES app.orders (id, is_test_fixture),
    FOREIGN KEY (menu_item_id, is_test_fixture) REFERENCES app.menu_items (id, is_test_fixture)
);
CREATE INDEX order_items_order_idx ON app.order_items (order_id);

-- Only ACTIVE recipe versions may be pinned (DDR-10).
CREATE FUNCTION app.check_recipe_pin() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    IF NEW.recipe_version_id IS NOT NULL
       AND (TG_OP = 'INSERT' OR NEW.recipe_version_id IS DISTINCT FROM OLD.recipe_version_id)
       AND NOT EXISTS (SELECT 1 FROM app.recipe_versions v
                        WHERE v.id = NEW.recipe_version_id AND v.status = 'ACTIVE') THEN
        RAISE EXCEPTION 'only an ACTIVE recipe version can be pinned to an order item'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------- payments (#15 §9, PL-07/08)
CREATE TABLE app.payments (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id         uuid NOT NULL,
    method           text NOT NULL CHECK (method IN ('SIM_UPI', 'SIM_CARD', 'COD')),
    status           text NOT NULL CHECK (status IN ({_in(PAYMENT)})),
    is_test_fixture  boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (order_id, is_test_fixture) REFERENCES app.orders (id, is_test_fixture),
    -- COD and prepaid use separate status families (Matrix §7.2).
    CONSTRAINT payments_status_family CHECK (
        (method = 'COD' AND status IN ('COLLECTION_PENDING', 'COLLECTED', 'MISMATCH')) OR
        (method <> 'COD' AND status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT',
                                        'REFUND_PENDING', 'REFUNDED'))
    )
);
CREATE INDEX payments_order_idx ON app.payments (order_id);

-- ---------------------------------------------------------------- delivery assignments (#7 §3)
CREATE TABLE app.delivery_assignments (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id       uuid NOT NULL REFERENCES app.orders (id),
    agent_user_id  uuid NOT NULL REFERENCES app.users (id),
    status         text NOT NULL CHECK (status IN ({_in(ASSIGNMENT)})),
    offered_at     timestamptz NOT NULL DEFAULT now(),
    responded_at   timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
-- DL-03: one active delivery per agent.
CREATE UNIQUE INDEX delivery_assignments_one_active_per_agent_uq
    ON app.delivery_assignments (agent_user_id) WHERE status IN ('ACCEPTED', 'FAILURE_REQUESTED');
-- At most one live assignment per order (reassignment revokes the previous one first, DL-07).
CREATE UNIQUE INDEX delivery_assignments_one_live_per_order_uq
    ON app.delivery_assignments (order_id) WHERE status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED');

-- ---------------------------------------------------------------- triggers
CREATE TRIGGER a_orders_transition BEFORE INSERT OR UPDATE OF fulfilment_status ON app.orders
    FOR EACH ROW EXECUTE FUNCTION app.enforce_status_transition('fulfilment', 'fulfilment_status');
CREATE TRIGGER orders_touch BEFORE UPDATE ON app.orders FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

CREATE TRIGGER a_order_items_transition BEFORE INSERT OR UPDATE OF prep_status ON app.order_items
    FOR EACH ROW EXECUTE FUNCTION app.enforce_status_transition('item', 'prep_status');
CREATE TRIGGER b_order_items_recipe_pin BEFORE INSERT OR UPDATE OF recipe_version_id ON app.order_items
    FOR EACH ROW EXECUTE FUNCTION app.check_recipe_pin();

CREATE TRIGGER a_payments_transition BEFORE INSERT OR UPDATE OF status ON app.payments
    FOR EACH ROW EXECUTE FUNCTION app.enforce_status_transition('payment', 'status');
CREATE TRIGGER payments_touch BEFORE UPDATE ON app.payments FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

CREATE TRIGGER a_delivery_assignments_transition BEFORE INSERT OR UPDATE OF status ON app.delivery_assignments
    FOR EACH ROW EXECUTE FUNCTION app.enforce_status_transition('assignment', 'status');
CREATE TRIGGER delivery_assignments_touch BEFORE UPDATE ON app.delivery_assignments
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS app.delivery_assignments;
DROP TABLE IF EXISTS app.payments;
DROP TABLE IF EXISTS app.order_items;
DROP TABLE IF EXISTS app.orders;
DROP FUNCTION IF EXISTS app.check_recipe_pin();
DELETE FROM app.status_initial;
DELETE FROM app.status_transitions;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
