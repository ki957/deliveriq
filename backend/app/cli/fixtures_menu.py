"""TEST menu fixtures (DDR-48, DDR-50, DDR-54, DDR-106, DDR-107). Local/test only; run via `make fixtures`.

Written from scratch, never derived from the Kitchen SOP. Rows that carry `is_test_fixture` are
inserted here as the loader (no API can set the flag). Activation and publication then go through
the same services, RBAC and database rules as live users: the seed Kitchen Manager submits,
validates, records four sign-offs and activates; the seed Central Administrator records the
product-owner sign-off and publishes. Re-running adds nothing.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Connection, text

from app.core.db import get_engine
from app.core.permissions import Principal
from app.modules.identity import service as identity
from app.modules.menu import service as menu
from app.modules.recipes import service as recipes
from app.modules.recipes.domain import CA_SIGNOFFS

_NS = uuid.UUID("7e2b9c1a-4f60-4d1e-8a3b-2c5d9e0f1a77")  # fixed namespace: re-runs reuse the same IDs
KITCHEN_CODE = "KIT-CHN-001"
CATEGORY = "TEST – Category"
TEXT = "TEST – synthetic, not a real recipe"
DESCRIPTION = "TEST – synthetic dish for workflow testing"
LINE_GRAMS = 100
# (letter, price in paise, ingredient numbers, activated and published?) — DDR-106, DDR-107.
DISHES: tuple[tuple[str, int, tuple[int, int], bool], ...] = (
    ("A", 11100, (1, 2), True),
    ("B", 22200, (3, 4), True),
    ("C", 33300, (5, 6), True),
    ("D", 44400, (1, 6), False),
)
INGREDIENTS = tuple(f"TEST – Ingredient {n}" for n in range(1, 7))
KM_MOBILE = "+910000000004"
CA_MOBILE = "+910000000006"
REASON = "TEST fixture loader (DDR-106)"
E2E_PREFIX = "TEST – E2E "
TEST_COUPON = ("TEST50", 5000)  # DDR-110 (3): ₹50, no minimum, no usage limit


def dish_name(letter: str) -> str:
    return f"TEST – Synthetic Dish {letter}"


def fixture_names() -> list[str]:
    return [dish_name(letter) for letter, *_ in DISHES] + list(INGREDIENTS) + [CATEGORY]


def _id(*parts: str) -> uuid.UUID:
    return uuid.uuid5(_NS, "|".join(parts))


def _system(conn: Connection) -> None:
    conn.execute(
        text("SELECT set_config('app.actor_role', 'SYSTEM', true), set_config('app.reason', :r, true)"),
        {"r": REASON},
    )


def _principal(conn: Connection, mobile: str) -> Principal:
    user_id = conn.execute(
        text("SELECT id FROM app.users WHERE mobile_e164 = :m"), {"m": mobile}
    ).scalar_one_or_none()
    principal = identity.principal_for_user(user_id) if user_id else None
    if principal is None:
        raise RuntimeError(f"seed user {mobile[-2:]} missing: run `load-users` first")
    return principal


def _insert_dish(
    conn: Connection,
    letter: str,
    name: str,
    price: int,
    numbers: tuple[int, int],
    kitchen: uuid.UUID,
    category: uuid.UUID,
) -> tuple[int, int]:
    """One TEST recipe (version 1, DRAFT), its ingredient lines and a DRAFT menu item; insert-if-absent."""
    recipe, version = _id("recipe", letter), _id("recipe_version", letter, "1")
    recipes_added = conn.execute(
        text(
            "INSERT INTO app.recipes (id, kitchen_id, name) SELECT :id, :k, :n "
            "WHERE NOT EXISTS (SELECT 1 FROM app.recipes WHERE id = :id)"
        ),
        {"id": recipe, "k": kitchen, "n": name},
    ).rowcount
    conn.execute(
        text(
            "INSERT INTO app.recipe_versions (id, recipe_id, version, status, prep_type, portion, "
            "method, "
            "quality, inventory_rule, validation_text, is_test_fixture) "
            "SELECT :id, :r, 1, 'DRAFT', :t, :t, :t, :t, :t, :t, true "
            "WHERE NOT EXISTS (SELECT 1 FROM app.recipe_versions WHERE id = :id)"
        ),
        {"id": version, "r": recipe, "t": TEXT},
    )
    for line_no, number in enumerate(numbers, start=1):
        ingredient = conn.execute(
            text("SELECT id FROM app.ingredients WHERE lower(name) = lower(:n)"),
            {"n": INGREDIENTS[number - 1]},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO app.recipe_ingredients (id, recipe_version_id, line_no, ingredient_id, "
                "quantity, unit) "
                "SELECT :id, :v, :l, :i, :q, 'g' WHERE NOT EXISTS "
                "(SELECT 1 FROM app.recipe_ingredients WHERE recipe_version_id = :v AND line_no = :l)"
            ),
            {
                "id": _id("recipe_ingredient", letter, str(line_no)),
                "v": version,
                "l": line_no,
                "i": ingredient,
                "q": LINE_GRAMS,
            },
        )
    items_added = conn.execute(
        text(
            "INSERT INTO app.menu_items (id, kitchen_id, recipe_id, category_id, name, description, "
            "is_veg, "
            "spice_level, price_paise, tax_classification, prep_time_minutes, image_is_placeholder, "
            "publication_status, is_test_fixture) "
            "SELECT :id, :k, :r, :c, :n, :d, true, 'TEST', :p, 'TEST', 10, "
            "true, 'DRAFT', true WHERE NOT EXISTS (SELECT 1 FROM app.menu_items WHERE id = :id)"
        ),
        {
            "id": _id("menu_item", letter),
            "k": kitchen,
            "r": recipe,
            "c": category,
            "n": name,
            "d": DESCRIPTION,
            "p": price,
        },
    ).rowcount
    return recipes_added, items_added


def _insert_rows(conn: Connection) -> dict[str, int]:
    added = {"ingredients": 0, "recipes": 0, "menu_items": 0, "coupons": 0}
    _system(conn)
    kitchen = conn.execute(
        text("SELECT id FROM app.kitchens WHERE code = :c"), {"c": KITCHEN_CODE}
    ).scalar_one()
    conn.execute(
        text("INSERT INTO app.menu_categories (id, name) VALUES (:id, :n) ON CONFLICT (name) DO NOTHING"),
        {"id": _id("category"), "n": CATEGORY},
    )
    category = conn.execute(
        text("SELECT id FROM app.menu_categories WHERE name = :n"), {"n": CATEGORY}
    ).scalar_one()
    for name in INGREDIENTS:
        added["ingredients"] += conn.execute(
            text(
                "INSERT INTO app.ingredients (id, name, unit, origin) SELECT :id, :n, 'g', 'TEST_FIXTURE' "
                "WHERE NOT EXISTS (SELECT 1 FROM app.ingredients WHERE lower(name) = lower(:n))"
            ),
            {"id": _id("ingredient", name), "n": name},
        ).rowcount
    for letter, price, numbers, _published in DISHES:
        recipes_added, items_added = _insert_dish(
            conn, letter, dish_name(letter), price, numbers, kitchen, category
        )
        added["recipes"] += recipes_added
        added["menu_items"] += items_added
    # DDR-110 (3): one TEST coupon, local/test only, to prove a coupon may take the payable below ₹500.
    added["coupons"] = conn.execute(
        text(
            "INSERT INTO app.coupons "
            "(code, discount_paise, min_food_subtotal_paise, is_active, is_test_fixture) "
            "VALUES (:c, :d, 0, true, true) ON CONFLICT (code) DO NOTHING"
        ),
        {"c": TEST_COUPON[0], "d": TEST_COUPON[1]},
    ).rowcount
    return added


OPENING_STOCK_GRAMS = 10_000  # DDR-111 (8): 100 portions per TEST ingredient at 100 g per line


def load_stock() -> int:
    """TEST opening stock (DDR-37, DDR-111 (8)): test-only, flagged from the ingredient's origin.

    Inserted once per TEST ingredient with an OPENING ledger entry; re-running adds nothing and
    never resets stock that orders or adjustments have changed.
    """
    added = 0
    with get_engine().begin() as conn:
        _system(conn)
        kitchen = conn.execute(
            text("SELECT id FROM app.kitchens WHERE code = :c"), {"c": KITCHEN_CODE}
        ).scalar_one()
        for name in INGREDIENTS:
            ingredient = conn.execute(
                text(
                    "SELECT id FROM app.ingredients WHERE lower(name) = lower(:n) AND origin = 'TEST_FIXTURE'"
                ),
                {"n": name},
            ).scalar_one_or_none()
            if ingredient is None:
                raise RuntimeError("TEST menu missing: run `load-menu` first")
            inserted = conn.execute(
                text(
                    "INSERT INTO app.ingredient_stock (kitchen_id, ingredient_id, on_hand) "
                    "VALUES (:k, :i, :q) ON CONFLICT (kitchen_id, ingredient_id) DO NOTHING"
                ),
                {"k": kitchen, "i": ingredient, "q": OPENING_STOCK_GRAMS},
            ).rowcount
            if inserted:
                conn.execute(
                    text(
                        "INSERT INTO app.stock_movements (kitchen_id, ingredient_id, delta, kind, reason, "
                        "actor_role) VALUES (:k, :i, :q, 'OPENING', :r, 'SYSTEM')"
                    ),
                    {
                        "k": kitchen,
                        "i": ingredient,
                        "q": OPENING_STOCK_GRAMS,
                        "r": "TEST opening stock (DDR-37)",
                    },
                )
                added += 1
    return added


def load_e2e_recipe() -> str:
    """A fresh DRAFT TEST recipe and menu item for one E2E workflow run (DDR-108).

    Uses Dish D's approved definition (Ingredients 1 + 6, ₹444) under the name `TEST – E2E <n>`.
    """
    _letter, price, numbers, _live = DISHES[3]
    with get_engine().begin() as conn:
        _system(conn)
        if not conn.execute(
            text("SELECT count(*) FROM app.ingredients WHERE origin = 'TEST_FIXTURE'")
        ).scalar_one():
            raise RuntimeError("TEST menu missing: run `load-menu` first")
        number = (
            1
            + conn.execute(
                text("SELECT count(*) FROM app.recipes WHERE name LIKE :p"), {"p": E2E_PREFIX + "%"}
            ).scalar_one()
        )
        name = f"{E2E_PREFIX}{number}"
        kitchen = conn.execute(
            text("SELECT id FROM app.kitchens WHERE code = :c"), {"c": KITCHEN_CODE}
        ).scalar_one()
        category = conn.execute(
            text("SELECT id FROM app.menu_categories WHERE name = :n"), {"n": CATEGORY}
        ).scalar_one()
        _insert_dish(conn, f"e2e-{number}", name, price, numbers, kitchen, category)
    return name


def _activate(version: uuid.UUID, km: Principal, ca: Principal) -> bool:
    """Walk one TEST recipe to ACTIVE through the recipe service; True if anything changed."""
    changed = False
    for _ in range(4):  # DRAFT -> PENDING_VALIDATION -> VALIDATED -> ACTIVE
        detail = recipes.version_detail(km, version)
        status = detail.version.status
        if status == "ACTIVE":
            return changed
        if status == "DRAFT":
            recipes.transition(km, version, "submit", REASON)
        elif status == "PENDING_VALIDATION":
            recipes.transition(km, version, "validate", REASON)
        elif status == "VALIDATED":
            for kind in detail.missing_signoffs:
                signer = ca if kind in CA_SIGNOFFS else km
                recipes.record_signoff(signer, version, kind.value, REASON)
            recipes.transition(km, version, "activate", REASON)
        else:
            raise RuntimeError(f"TEST recipe {version} is {status}; reset local test data to reload it")
        changed = True
    return changed


def _publish(item: uuid.UUID, ca: Principal) -> bool:
    changed = False
    for action, source in (("mark_ready", "DRAFT"), ("publish", "READY_FOR_PUBLICATION")):
        status = next(i.publication_status for i in menu.list_items(ca) if i.id == item)
        if status == source:
            menu.transition(ca, item, action, REASON)
            changed = True
    return changed


def load_menu() -> dict[str, int]:
    with get_engine().begin() as conn:
        added = _insert_rows(conn)
        km, ca = _principal(conn, KM_MOBILE), _principal(conn, CA_MOBILE)
    activated = published = 0
    for letter, _price, _numbers, live in DISHES:
        if not live:
            continue
        activated += _activate(_id("recipe_version", letter, "1"), km, ca)
        published += _publish(_id("menu_item", letter), ca)
    return {**added, "activated": activated, "published": published}
