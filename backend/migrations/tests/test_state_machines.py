"""Database enforcement of the canonical status machines, recipe activation and menu publication."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from app.modules.delivery import domain as delivery
from app.modules.menu import domain as menu
from app.modules.orders import domain as orders
from app.modules.payments import domain as payments
from app.modules.recipes import domain as recipes

from .conftest import (
    INTEGRATION,
    Conn,
    act_as,
    make_test_recipe_version,
    make_user,
    one,
    seed_ids,
    sign_all,
    walk_recipe_to,
)

pytestmark = INTEGRATION

PYTHON_MACHINES: dict[str, tuple[frozenset[tuple[str, str]], frozenset[str]]] = {
    "fulfilment": (orders.FULFILMENT_TRANSITIONS, orders.FULFILMENT_INITIAL),
    "item": (orders.ITEM_TRANSITIONS, orders.ITEM_INITIAL),
    "payment": (payments.PAYMENT_TRANSITIONS, payments.PAYMENT_INITIAL),
    "assignment": (delivery.ASSIGNMENT_TRANSITIONS, delivery.ASSIGNMENT_INITIAL),
    "recipe": (recipes.RECIPE_TRANSITIONS, recipes.RECIPE_INITIAL),
    "menu": (menu.MENU_TRANSITIONS, menu.MENU_INITIAL),
}


# ---------------------------------------------------------------- one definition, two enforcers
@pytest.mark.parametrize("machine", sorted(PYTHON_MACHINES))
def test_database_and_domain_define_identical_machines(api: Conn, machine: str) -> None:
    transitions, initial = PYTHON_MACHINES[machine]
    db_transitions = {
        (str(a), str(b))
        for a, b in api.execute(
            "SELECT from_status, to_status FROM app.status_transitions WHERE machine = %s", (machine,)
        ).fetchall()
    }
    db_initial = {
        str(r[0]) for r in api.execute("SELECT status FROM app.status_initial WHERE machine = %s", (machine,))
    }
    assert db_transitions == {(str(a), str(b)) for a, b in transitions}
    assert db_initial == {str(s) for s in initial}


# ---------------------------------------------------------------- helpers
def _order(conn: Conn, customer: uuid.UUID, *, fixture: bool = False) -> uuid.UUID:
    """Real orders omit is_test_fixture (runtime roles cannot write it); fixtures set it as the loader."""
    ids = seed_ids(conn)
    act_as(conn, "CUSTOMER", customer)
    if not fixture:
        return one(  # type: ignore[return-value]
            conn,
            """INSERT INTO app.orders (customer_user_id, kitchen_id, region_id, fulfilment_status)
               VALUES (%s, %s, %s, 'PLACED') RETURNING id""",
            (customer, ids.kitchen, ids.region),
        )
    return one(  # type: ignore[return-value]
        conn,
        """INSERT INTO app.orders (customer_user_id, kitchen_id, region_id, fulfilment_status, is_test_fixture)
           VALUES (%s, %s, %s, 'PLACED', true) RETURNING id""",
        (customer, ids.kitchen, ids.region),
    )


def _set_order(
    conn: Conn, order: uuid.UUID, status: str, role: str, user: uuid.UUID | None, reason: str = ""
) -> None:
    act_as(conn, role, user, reason=reason)
    conn.execute("UPDATE app.orders SET fulfilment_status = %s WHERE id = %s", (status, order))


# ---------------------------------------------------------------- fulfilment
def test_full_happy_path_records_history(api: Conn) -> None:
    customer = make_user(api, "Path customer", "CUSTOMER")
    staff = make_user(api, "Path staff", "KITCHEN_STAFF")
    agent = make_user(api, "Path agent", "DELIVERY_AGENT")
    order = _order(api, customer)
    for status, role, user in [
        ("PENDING_KITCHEN", "SYSTEM", None),
        ("ACCEPTED", "KITCHEN_STAFF", staff),
        ("PREPARING", "KITCHEN_STAFF", staff),
        ("READY_FOR_PICKUP", "SYSTEM", None),
        ("PICKED_UP", "DELIVERY_AGENT", agent),
        ("OUT_FOR_DELIVERY", "DELIVERY_AGENT", agent),
        ("DELIVERED", "SYSTEM", None),
    ]:
        _set_order(api, order, status, role, user)
    history = api.execute(
        "SELECT from_status, to_status, actor_role FROM app.status_history WHERE entity_id = %s ORDER BY id",
        (order,),
    ).fetchall()
    assert [h[1] for h in history] == [
        "PLACED", "PENDING_KITCHEN", "ACCEPTED", "PREPARING", "READY_FOR_PICKUP",
        "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED",
    ]  # fmt: skip
    assert history[0][0] is None


@pytest.mark.parametrize(
    ("path", "illegal"),
    [
        ([], "ACCEPTED"),  # PLACED -> ACCEPTED skips payment/kitchen eligibility
        ([], "DELIVERED"),
        (["PENDING_KITCHEN", "ACCEPTED"], "CANCELLED"),  # CU-19: no cancel after acceptance
        (["PENDING_KITCHEN", "ACCEPTED"], "OUT_FOR_DELIVERY"),
        (["PENDING_KITCHEN", "ACCEPTED", "PREPARING"], "PICKED_UP"),  # KI-08: blocked until Ready
        (["CANCELLED"], "PENDING_KITCHEN"),  # terminal
    ],
)
def test_illegal_fulfilment_transitions_are_rejected(api: Conn, path: list[str], illegal: str) -> None:
    customer = make_user(api, "Illegal customer", "CUSTOMER")
    order = _order(api, customer)
    for status in path:
        _set_order(api, order, status, "SYSTEM", None)
    with pytest.raises(psycopg.errors.CheckViolation, match="illegal fulfilment transition"):
        _set_order(api, order, illegal, "SYSTEM", None)


def test_order_must_start_placed(api: Conn) -> None:
    customer = make_user(api, "Start customer", "CUSTOMER")
    ids = seed_ids(api)
    act_as(api, "CUSTOMER", customer)
    with pytest.raises(psycopg.errors.CheckViolation, match="illegal initial fulfilment"):
        api.execute(
            "INSERT INTO app.orders (customer_user_id, kitchen_id, region_id, fulfilment_status) "
            "VALUES (%s, %s, %s, 'ACCEPTED')",
            (customer, ids.kitchen, ids.region),
        )


def test_status_change_without_actor_context_is_rejected(api: Conn) -> None:
    customer = make_user(api, "Actor customer", "CUSTOMER")
    order = _order(api, customer)
    api.execute("SELECT set_config('app.actor_role', '', true)")
    with pytest.raises(psycopg.errors.CheckViolation, match=r"requires app\.actor_role"):
        api.execute("UPDATE app.orders SET fulfilment_status = 'PENDING_KITCHEN' WHERE id = %s", (order,))


def test_human_actor_needs_a_user_id(api: Conn) -> None:
    customer = make_user(api, "Actor id customer", "CUSTOMER")
    order = _order(api, customer)
    with pytest.raises(psycopg.errors.CheckViolation, match=r"requires app\.actor_user_id"):
        _set_order(api, order, "PENDING_KITCHEN", "KITCHEN_STAFF", None)


def test_kitchen_rejection_requires_reason(api: Conn) -> None:
    customer = make_user(api, "Reject customer", "CUSTOMER")
    staff = make_user(api, "Reject staff", "KITCHEN_STAFF")
    order = _order(api, customer)
    _set_order(api, order, "PENDING_KITCHEN", "SYSTEM", None)
    api.execute("SAVEPOINT s")
    with pytest.raises(psycopg.errors.CheckViolation, match="requires a reason"):
        _set_order(api, order, "REJECTED", "KITCHEN_STAFF", staff)
    api.execute("ROLLBACK TO SAVEPOINT s")
    _set_order(api, order, "REJECTED", "KITCHEN_STAFF", staff, reason="Ingredient shortage")
    assert one(api, "SELECT reason FROM app.status_history WHERE entity_id = %s ORDER BY id DESC LIMIT 1",
               (order,)) == "Ingredient shortage"  # fmt: skip


def test_special_instructions_limit_is_250(api: Conn) -> None:
    customer = make_user(api, "Notes customer", "CUSTOMER")
    order = _order(api, customer)
    api.execute("UPDATE app.orders SET special_instructions = %s WHERE id = %s", ("x" * 250, order))
    with pytest.raises(psycopg.errors.CheckViolation):
        api.execute("UPDATE app.orders SET special_instructions = %s WHERE id = %s", ("x" * 251, order))


# ---------------------------------------------------------------- assignment vs fulfilment (DDR-16)
def test_assignment_changes_never_touch_fulfilment(api: Conn) -> None:
    customer = make_user(api, "Assign customer", "CUSTOMER")
    staff = make_user(api, "Assign staff", "KITCHEN_STAFF")
    agent = make_user(api, "Assign agent", "DELIVERY_AGENT")
    order = _order(api, customer)
    _set_order(api, order, "PENDING_KITCHEN", "SYSTEM", None)
    _set_order(api, order, "ACCEPTED", "KITCHEN_STAFF", staff)
    act_as(api, "SYSTEM")
    assignment = one(
        api,
        "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) "
        "VALUES (%s, %s, 'OFFERED') RETURNING id",
        (order, agent),
    )
    for status, reason in [("ACCEPTED", ""), ("REVOKED", "Reassigned by manager")]:
        act_as(api, "DELIVERY_AGENT" if status == "ACCEPTED" else "REGIONAL_MANAGER",
               agent if status == "ACCEPTED" else make_user(api, "RM", "REGIONAL_MANAGER"), reason=reason)  # fmt: skip
        api.execute("UPDATE app.delivery_assignments SET status = %s WHERE id = %s", (status, assignment))
        assert one(api, "SELECT fulfilment_status FROM app.orders WHERE id = %s", (order,)) == "ACCEPTED"


def test_one_live_assignment_per_agent(api: Conn) -> None:
    """DL-03 one active delivery, tightened by DDR-111 (6): one open offer or live delivery per agent."""
    agent = make_user(api, "Busy agent", "DELIVERY_AGENT")
    orders = [_order(api, make_user(api, "Busy customer", "CUSTOMER")) for _ in range(2)]
    act_as(api, "SYSTEM")
    first = one(
        api,
        "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) "
        "VALUES (%s, %s, 'OFFERED') RETURNING id",
        (orders[0], agent),
    )
    insert_second = (
        "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) VALUES (%s, %s, 'OFFERED')"
    )
    api.execute("SAVEPOINT offered")
    with pytest.raises(psycopg.errors.UniqueViolation, match="one_live_per_agent"):
        api.execute(insert_second, (orders[1], agent))
    api.execute("ROLLBACK TO SAVEPOINT offered")
    act_as(api, "DELIVERY_AGENT", agent)
    api.execute("UPDATE app.delivery_assignments SET status = 'ACCEPTED' WHERE id = %s", (first,))
    act_as(api, "SYSTEM")
    with pytest.raises(psycopg.errors.UniqueViolation):
        api.execute(insert_second, (orders[1], agent))


def test_illegal_assignment_and_item_transitions(api: Conn) -> None:
    agent = make_user(api, "Item agent", "DELIVERY_AGENT")
    customer = make_user(api, "Item customer", "CUSTOMER")
    order = _order(api, customer)
    act_as(api, "SYSTEM")
    assignment = one(api, "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) "
                          "VALUES (%s, %s, 'OFFERED') RETURNING id", (order, agent))  # fmt: skip
    api.execute("SAVEPOINT s")
    with pytest.raises(psycopg.errors.CheckViolation, match="illegal assignment transition"):
        api.execute("UPDATE app.delivery_assignments SET status = 'COMPLETED' WHERE id = %s", (assignment,))
    api.execute("ROLLBACK TO SAVEPOINT s")
    with pytest.raises(psycopg.errors.CheckViolation, match="requires a reason"):
        api.execute("UPDATE app.delivery_assignments SET status = 'REJECTED' WHERE id = %s", (assignment,))


# ---------------------------------------------------------------- payments
def test_payment_families_and_transitions(api: Conn) -> None:
    customer = make_user(api, "Pay customer", "CUSTOMER")
    order = _order(api, customer)
    act_as(api, "SYSTEM")
    api.execute("SAVEPOINT s")
    with pytest.raises(psycopg.errors.CheckViolation, match="payments_status_family"):
        api.execute(
            "INSERT INTO app.payments (order_id, method, status) VALUES (%s, 'COD', 'PENDING')", (order,)
        )
    api.execute("ROLLBACK TO SAVEPOINT s")
    payment = one(api, "INSERT INTO app.payments (order_id, method, status) "
                       "VALUES (%s, 'SIM_UPI', 'PENDING') RETURNING id", (order,))  # fmt: skip
    api.execute("UPDATE app.payments SET status = 'FAILED' WHERE id = %s", (payment,))
    with pytest.raises(psycopg.errors.CheckViolation, match="illegal payment transition"):
        api.execute("UPDATE app.payments SET status = 'SUCCEEDED' WHERE id = %s", (payment,))


# ---------------------------------------------------------------- fixture isolation (plan §5.2)
def test_real_order_cannot_contain_test_menu_item(migrator: Conn) -> None:
    version = make_test_recipe_version(migrator)
    recipe = one(migrator, "SELECT recipe_id FROM app.recipe_versions WHERE id = %s", (version,))
    ids = seed_ids(migrator)
    item = one(migrator, """INSERT INTO app.menu_items (kitchen_id, recipe_id, name, publication_status,
                                                        is_test_fixture)
                             VALUES (%s, %s, 'TEST – Isolation dish', 'DRAFT', true) RETURNING id""",
               (ids.kitchen, recipe))  # fmt: skip
    customer = make_user(migrator, "Isolation customer", "CUSTOMER")
    real_order = _order(migrator, customer, fixture=False)
    act_as(migrator, "SYSTEM")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        migrator.execute(
            "INSERT INTO app.order_items (order_id, menu_item_id, quantity, prep_status, is_test_fixture) "
            "VALUES (%s, %s, 1, 'PENDING', false)",
            (real_order, item),
        )


@pytest.mark.parametrize(("name", "fixture"), [("TEST – Tagged", False), ("Untagged dish", True)])
def test_test_prefix_matches_fixture_flag(migrator: Conn, name: str, fixture: bool) -> None:
    version = make_test_recipe_version(migrator)
    recipe = one(migrator, "SELECT recipe_id FROM app.recipe_versions WHERE id = %s", (version,))
    with pytest.raises(psycopg.errors.CheckViolation, match="menu_items_test_prefix"):
        migrator.execute(
            "INSERT INTO app.menu_items (kitchen_id, recipe_id, name, publication_status, is_test_fixture) "
            "VALUES (%s, %s, %s, 'DRAFT', %s)",
            (seed_ids(migrator).kitchen, recipe, name, fixture),
        )


# ---------------------------------------------------------------- recipes (DDR-10, DDR-50, DDR-54)
def test_activation_needs_all_five_signoffs(migrator: Conn) -> None:
    km = make_user(migrator, "Activation KM", "KITCHEN_MANAGER")
    version = make_test_recipe_version(migrator)
    walk_recipe_to(migrator, version, "VALIDATED", km, km)
    for kind in ("CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER"):  # four of five
        migrator.execute("INSERT INTO app.recipe_signoffs (recipe_version_id, signoff_type, signed_by) "
                         "VALUES (%s, %s, %s)", (version, kind, km))  # fmt: skip
    act_as(migrator, "KITCHEN_MANAGER", km, reason="try activation")
    with pytest.raises(psycopg.errors.CheckViolation, match="all five sign-offs"):
        migrator.execute("UPDATE app.recipe_versions SET status = 'ACTIVE' WHERE id = %s", (version,))


def test_kitchen_manager_activates_with_five_signoffs(migrator: Conn) -> None:
    km = make_user(migrator, "Activation KM", "KITCHEN_MANAGER")
    version = make_test_recipe_version(migrator)
    walk_recipe_to(migrator, version, "ACTIVE", km, km)
    assert one(migrator, "SELECT status FROM app.recipe_versions WHERE id = %s", (version,)) == "ACTIVE"


@pytest.mark.parametrize("role", ["KITCHEN_STAFF", "REGIONAL_MANAGER", "CENTRAL_ADMIN"])
def test_only_kitchen_manager_can_activate(migrator: Conn, role: str) -> None:
    km = make_user(migrator, "KM", "KITCHEN_MANAGER")
    other = make_user(migrator, "Other", role)
    version = make_test_recipe_version(migrator)
    walk_recipe_to(migrator, version, "VALIDATED", km, km)
    sign_all(migrator, version, km)
    act_as(migrator, role, other, reason="not my call")
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="may not perform recipe transition"):
        migrator.execute("UPDATE app.recipe_versions SET status = 'ACTIVE' WHERE id = %s", (version,))


def test_sop_recipes_can_never_be_activated(migrator: Conn) -> None:
    km = make_user(migrator, "SOP KM", "KITCHEN_MANAGER")
    version = make_test_recipe_version(migrator, fixture=False)
    with pytest.raises(psycopg.errors.CheckViolation, match="poc_no_sop_activation"):
        walk_recipe_to(migrator, version, "ACTIVE", km, km)


def test_quarantined_recipe_cannot_be_submitted(migrator: Conn) -> None:
    km = make_user(migrator, "Quarantine KM", "KITCHEN_MANAGER")
    ids = seed_ids(migrator)
    act_as(migrator, "SYSTEM")
    recipe = one(migrator, "INSERT INTO app.recipes (kitchen_id, name) VALUES (%s, 'Duplicate candidate') "
                           "RETURNING id", (ids.kitchen,))  # fmt: skip
    version = one(migrator, """INSERT INTO app.recipe_versions (recipe_id, version, status, source_sha256,
                                                                quarantine_reason)
                                VALUES (%s, 1, 'QUARANTINED_DUPLICATE_CANDIDATE', %s, 'DDR-13 duplicate')
                                RETURNING id""", (recipe, "0" * 64))  # fmt: skip
    act_as(migrator, "KITCHEN_MANAGER", km, reason="submit")
    with pytest.raises(psycopg.errors.CheckViolation, match="illegal recipe transition"):
        migrator.execute(
            "UPDATE app.recipe_versions SET status = 'PENDING_VALIDATION' WHERE id = %s", (version,)
        )


def test_only_active_versions_can_be_pinned(migrator: Conn) -> None:
    version = make_test_recipe_version(migrator)  # DRAFT
    recipe = one(migrator, "SELECT recipe_id FROM app.recipe_versions WHERE id = %s", (version,))
    item = one(migrator, """INSERT INTO app.menu_items (kitchen_id, recipe_id, name, publication_status,
                                                        is_test_fixture)
                             VALUES (%s, %s, 'TEST – Pin dish', 'DRAFT', true) RETURNING id""",
               (seed_ids(migrator).kitchen, recipe))  # fmt: skip
    customer = make_user(migrator, "Pin customer", "CUSTOMER")
    order = _order(migrator, customer, fixture=True)
    act_as(migrator, "SYSTEM")
    with pytest.raises(psycopg.errors.CheckViolation, match="only an ACTIVE recipe version"):
        migrator.execute(
            "INSERT INTO app.order_items (order_id, menu_item_id, recipe_version_id, quantity, prep_status, "
            "is_test_fixture) VALUES (%s, %s, %s, 1, 'PENDING', true)",
            (order, item, version),
        )


# ---------------------------------------------------------------- menu publication (DDR-11, DDR-31)
def _ready_item(conn: Conn, recipe: object) -> uuid.UUID:
    category = one(conn, "INSERT INTO app.menu_categories (name) VALUES (%s) RETURNING id",
                   ("TEST category " + uuid.uuid4().hex[:6],))  # fmt: skip
    return one(  # type: ignore[return-value]
        conn,
        """INSERT INTO app.menu_items (kitchen_id, recipe_id, category_id, name, description, is_veg,
                                       spice_level, price_paise, tax_classification, prep_time_minutes,
                                       image_is_placeholder, publication_status, is_test_fixture)
           VALUES (%s, %s, %s, 'TEST – Publish dish', 'Synthetic test dish', true, 'TEST', 1, 'TEST', 1,
                   true, 'DRAFT', true) RETURNING id""",
        (seed_ids(conn).kitchen, recipe, category),
    )


def test_publication_requires_an_active_recipe(migrator: Conn) -> None:
    version = make_test_recipe_version(migrator)  # DRAFT recipe
    recipe = one(migrator, "SELECT recipe_id FROM app.recipe_versions WHERE id = %s", (version,))
    item = _ready_item(migrator, recipe)
    act_as(migrator, "SYSTEM")
    with pytest.raises(psycopg.errors.CheckViolation, match="active recipe version"):
        migrator.execute("UPDATE app.menu_items SET publication_status = 'READY_FOR_PUBLICATION' WHERE id = %s",
                         (item,))  # fmt: skip


def test_regional_manager_publishes_and_it_is_audited(migrator: Conn) -> None:
    km = make_user(migrator, "Publish KM", "KITCHEN_MANAGER")
    rm = make_user(migrator, "Publish RM", "REGIONAL_MANAGER")
    version = make_test_recipe_version(migrator)
    walk_recipe_to(migrator, version, "ACTIVE", km, km)
    recipe = one(migrator, "SELECT recipe_id FROM app.recipe_versions WHERE id = %s", (version,))
    item = _ready_item(migrator, recipe)
    act_as(migrator, "SYSTEM")
    migrator.execute("UPDATE app.menu_items SET publication_status = 'READY_FOR_PUBLICATION' WHERE id = %s",
                     (item,))  # fmt: skip
    act_as(migrator, "KITCHEN_MANAGER", km)
    migrator.execute("SAVEPOINT s")
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="may not perform menu transition"):
        migrator.execute("UPDATE app.menu_items SET publication_status = 'PUBLISHED' WHERE id = %s", (item,))
    migrator.execute("ROLLBACK TO SAVEPOINT s")
    act_as(migrator, "REGIONAL_MANAGER", rm)
    migrator.execute("UPDATE app.menu_items SET publication_status = 'PUBLISHED' WHERE id = %s", (item,))
    audit = migrator.execute(
        "SELECT to_status, actor_role, actor_user_id, region_id FROM audit.menu_publications "
        "WHERE menu_item_id = %s ORDER BY id DESC LIMIT 1",
        (item,),
    ).fetchone()
    assert audit == ("PUBLISHED", "REGIONAL_MANAGER", rm, seed_ids(migrator).region)
