"""Recipe approval and menu publication over real HTTP and the real database (plan Task 5 criteria).

Needs the core stack and the seed users (`make up`, `make fixtures`, `make test-integration`).
Each run creates its own `TEST – Integration …` recipe and menu item in KIT-CHN-001. They stay in the
local/test database because sign-offs and audit rows are append-only by design; they are flagged
fixtures and never reach a production database (the production startup check refuses them).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
import pytest
from sqlalchemy import URL, create_engine, pool

from app.cli.fixtures import SEED_USERS
from app.modules.identity.tests.test_auth_integration import World, login
from app.shared.fixture_guard import FixtureRowsPresent, assert_no_fixtures, fixture_counts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

MOBILE = {role: mobile for _name, mobile, role, _r, _k in SEED_USERS}
REASON = {"reason": "integration test"}


@dataclass
class Item:
    recipe: uuid.UUID
    version: uuid.UUID
    menu_item: uuid.UUID


def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def new_test_item(world: World, *, description: str | None = "TEST – integration dish") -> Item:
    """A DRAFT TEST recipe with one ingredient line and a DRAFT menu item, inserted as the loader."""
    tag = uuid.uuid4().hex[:8]
    with world.db.transaction():
        world.db.execute("SELECT set_config('app.actor_role', 'SYSTEM', true)")
        recipe = scalar(
            world,
            "INSERT INTO app.recipes (kitchen_id, name) VALUES (%s, %s) RETURNING id",
            world.kitchen_a,
            f"TEST – Integration {tag}",
        )
        version = scalar(
            world,
            "INSERT INTO app.recipe_versions (recipe_id, version, status, is_test_fixture) "
            "VALUES (%s, 1, 'DRAFT', true) RETURNING id",
            recipe,
        )
        ingredient = scalar(world, "SELECT id FROM app.ingredients WHERE name = 'TEST – Ingredient 1'")
        world.db.execute(
            "INSERT INTO app.recipe_ingredients (recipe_version_id, line_no, ingredient_id, quantity, unit) "
            "VALUES (%s, 1, %s, 100, 'g')",
            (version, ingredient),
        )
        category = scalar(world, "SELECT id FROM app.menu_categories WHERE name = 'TEST – Category'")
        item = scalar(
            world,
            "INSERT INTO app.menu_items (kitchen_id, recipe_id, category_id, name, description, is_veg, spice_level, "
            "price_paise, tax_classification, prep_time_minutes, image_is_placeholder, publication_status, "
            "is_test_fixture) VALUES (%s, %s, %s, %s, %s, true, 'TEST', 12300, 'TEST', 10, true, 'DRAFT', true) "
            "RETURNING id",
            world.kitchen_a,
            recipe,
            category,
            f"TEST – Integration {tag}",
            description,
        )
    return Item(recipe, version, item)


@pytest.fixture(scope="module")
def seeded(world: World) -> dict[str, httpx.Client]:
    missing = [
        m
        for m in MOBILE.values()
        if not scalar(world, "SELECT count(*) FROM app.users WHERE mobile_e164 = %s", m)
    ]
    assert not missing, "seed users missing: run `make fixtures`"
    assert scalar(world, "SELECT count(*) FROM app.ingredients WHERE origin = 'TEST_FIXTURE'"), (
        "run `make fixtures`"
    )
    portals = {
        "KITCHEN_MANAGER": "kitchen",
        "KITCHEN_STAFF": "kitchen",
        "REGIONAL_MANAGER": "management",
        "CENTRAL_ADMIN": "management",
        "CUSTOMER": "customer",
        "DELIVERY_AGENT": "delivery",
    }
    return {role: login(MOBILE[role], portal) for role, portal in portals.items()}


def act(c: httpx.Client, version: uuid.UUID, action: str) -> httpx.Response:
    return c.post(f"/api/v1/recipes/versions/{version}/transitions", json={"action": action, **REASON})


def sign(c: httpx.Client, version: uuid.UUID, kind: str) -> httpx.Response:
    return c.post(
        f"/api/v1/recipes/versions/{version}/signoffs", json={"signoff_type": kind, "note": "integration"}
    )


def walk_to_validated(seeded: dict[str, httpx.Client], item: Item) -> None:
    km = seeded["KITCHEN_MANAGER"]
    assert act(km, item.version, "submit").status_code == 200
    assert act(km, item.version, "validate").status_code == 200


def sign_all(seeded: dict[str, httpx.Client], item: Item) -> None:
    for kind in ("CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER"):
        assert sign(seeded["KITCHEN_MANAGER"], item.version, kind).status_code == 204, kind
    assert sign(seeded["CENTRAL_ADMIN"], item.version, "PRODUCT_OWNER").status_code == 204


# ---------------------------------------------------------------- recipe approval
def test_only_the_km_activates_and_only_with_all_five_signoffs(
    world: World, seeded: dict[str, httpx.Client]
) -> None:
    item = new_test_item(world)
    km, ca = seeded["KITCHEN_MANAGER"], seeded["CENTRAL_ADMIN"]
    walk_to_validated(seeded, item)
    for kind in ("CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER"):
        assert sign(km, item.version, kind).status_code == 204
    missing = act(km, item.version, "activate")
    assert missing.status_code == 409 and "PRODUCT_OWNER" in missing.json()["message"]
    assert sign(km, item.version, "PRODUCT_OWNER").status_code == 403  # a CA account records it (DDR-106)
    assert sign(ca, item.version, "PRODUCT_OWNER").status_code == 204
    assert sign(ca, item.version, "PRODUCT_OWNER").status_code == 409  # recorded once

    # Five sign-offs do not activate by themselves.
    detail = km.get(f"/api/v1/recipes/versions/{item.version}").json()
    assert detail["status"] == "VALIDATED" and detail["missing_signoffs"] == []

    for role in ("KITCHEN_STAFF", "REGIONAL_MANAGER", "CENTRAL_ADMIN", "CUSTOMER", "DELIVERY_AGENT"):
        assert act(seeded[role], item.version, "activate").status_code == 403, role
    activated = act(km, item.version, "activate")
    assert activated.status_code == 200 and activated.json()["status"] == "ACTIVE"

    history = world.db.execute(
        "SELECT to_status, actor_role, reason, actor_user_id IS NOT NULL FROM app.status_history "
        "WHERE machine = 'recipe' AND entity_id = %s AND from_status IS NOT NULL ORDER BY id",
        (item.version,),
    ).fetchall()
    assert history == [
        ("PENDING_VALIDATION", "KITCHEN_MANAGER", "integration test", True),
        ("VALIDATED", "KITCHEN_MANAGER", "integration test", True),
        ("ACTIVE", "KITCHEN_MANAGER", "integration test", True),
    ]
    actions = [
        r[0]
        for r in world.db.execute(
            "SELECT action FROM audit.events WHERE target_id = %s ORDER BY occurred_at", (str(item.version),)
        ).fetchall()
    ]
    assert actions.count("recipe.signoff") == 5
    assert actions[-1] == "recipe.activate"


def test_return_and_reject_paths(world: World, seeded: dict[str, httpx.Client]) -> None:
    km = seeded["KITCHEN_MANAGER"]
    item = new_test_item(world)
    assert act(km, item.version, "submit").status_code == 200
    assert act(km, item.version, "return").json()["status"] == "DRAFT"
    walk_to_validated(seeded, item)
    assert act(km, item.version, "reject").json()["status"] == "REJECTED"
    assert act(km, item.version, "submit").status_code == 409  # REJECTED is terminal
    no_reason = km.post(f"/api/v1/recipes/versions/{item.version}/transitions", json={"action": "submit"})
    assert no_reason.status_code == 422


def test_kitchen_staff_view_only(world: World, seeded: dict[str, httpx.Client]) -> None:
    ks = seeded["KITCHEN_STAFF"]
    item = new_test_item(world)
    assert ks.get(f"/api/v1/recipes/versions/{item.version}").status_code == 200
    assert ks.get("/api/v1/recipes/review-items?status=OPEN").status_code == 200
    assert act(ks, item.version, "submit").status_code == 403
    assert sign(ks, item.version, "CHEF").status_code == 403
    for role in ("REGIONAL_MANAGER", "CUSTOMER", "DELIVERY_AGENT"):
        assert seeded[role].get("/api/v1/recipes/versions").status_code == 403, role
        assert seeded[role].get("/api/v1/recipes/review-items").status_code == 403, role


def test_other_kitchen_cannot_see_or_act(world: World, seeded: dict[str, httpx.Client]) -> None:
    item = new_test_item(world)
    other = login(world.user("KITCHEN_MANAGER", region=world.region_b, kitchen=world.kitchen_b), "kitchen")
    assert other.get(f"/api/v1/recipes/versions/{item.version}").status_code == 404
    assert act(other, item.version, "submit").status_code == 404
    assert item.version not in [v["id"] for v in other.get("/api/v1/recipes/versions").json()]
    other.close()


def test_open_review_items_block_submission_until_acknowledged(
    world: World, seeded: dict[str, httpx.Client]
) -> None:
    km, ks = seeded["KITCHEN_MANAGER"], seeded["KITCHEN_STAFF"]
    item = new_test_item(world)
    review = scalar(
        world,
        "INSERT INTO app.recipe_review_items (recipe_version_id, reason_code, subject, detail, source_ref) "
        "VALUES (%s, 'AMBIGUOUS_INGREDIENT', 'TEST – Ingredient 1', 'integration test', 'test') RETURNING id",
        item.version,
    )
    blocked = act(km, item.version, "submit")
    assert blocked.status_code == 409 and "open review item" in blocked.json()["message"]
    assert (
        ks.post(f"/api/v1/recipes/review-items/{review}/acknowledge", json={"note": "seen"}).status_code
        == 403
    )
    assert (
        km.post(f"/api/v1/recipes/review-items/{review}/acknowledge", json={"note": "x"}).status_code == 422
    )
    acked = km.post(f"/api/v1/recipes/review-items/{review}/acknowledge", json={"note": "checked by KM"})
    assert acked.status_code == 200 and acked.json()["status"] == "ACKNOWLEDGED"
    assert (
        km.post(f"/api/v1/recipes/review-items/{review}/acknowledge", json={"note": "again"}).status_code
        == 409
    )
    assert act(km, item.version, "submit").status_code == 200


def test_sop_recipes_cannot_be_submitted_signed_or_activated(
    world: World, seeded: dict[str, httpx.Client]
) -> None:
    km, ca = seeded["KITCHEN_MANAGER"], seeded["CENTRAL_ADMIN"]
    quarantined = scalar(world, "SELECT id FROM app.recipe_versions WHERE source_card_id = 'MENU008'")
    assert act(km, quarantined, "submit").status_code == 409
    flagged = scalar(
        world,
        "SELECT v.id FROM app.recipe_versions v WHERE v.status = 'DRAFT' AND NOT v.is_test_fixture AND EXISTS "
        "(SELECT 1 FROM app.recipe_review_items r WHERE r.recipe_version_id = v.id AND r.status = 'OPEN') LIMIT 1",
    )
    assert act(km, flagged, "submit").status_code == 409
    assert act(km, flagged, "activate").status_code == 409
    assert sign(km, flagged, "CHEF").status_code == 409  # TEST recipes only (DDR-54)
    assert sign(ca, flagged, "PRODUCT_OWNER").status_code == 404  # CA reads TEST recipes only
    assert (
        scalar(
            world, "SELECT count(*) FROM app.recipe_versions WHERE status = 'ACTIVE' AND NOT is_test_fixture"
        )
        == 0
    )


# ---------------------------------------------------------------- menu publication (DDR-31)
def publish_steps(c: httpx.Client, item: uuid.UUID) -> tuple[int, int]:
    ready = c.post(f"/api/v1/menu/manage/items/{item}/transitions", json={"action": "mark_ready"})
    publish = c.post(f"/api/v1/menu/manage/items/{item}/transitions", json={"action": "publish"})
    return ready.status_code, publish.status_code


def test_publication_needs_an_active_recipe_and_every_readiness_field(
    world: World, seeded: dict[str, httpx.Client]
) -> None:
    ca = seeded["CENTRAL_ADMIN"]
    inactive = new_test_item(world)
    refused = ca.post(
        f"/api/v1/menu/manage/items/{inactive.menu_item}/transitions", json={"action": "mark_ready"}
    )
    assert refused.status_code == 409 and "active recipe version" in refused.json()["message"]

    incomplete = new_test_item(world, description=None)
    walk_to_validated(seeded, incomplete)
    sign_all(seeded, incomplete)
    assert act(seeded["KITCHEN_MANAGER"], incomplete.version, "activate").status_code == 200
    refused = ca.post(
        f"/api/v1/menu/manage/items/{incomplete.menu_item}/transitions", json={"action": "mark_ready"}
    )
    assert refused.status_code == 409 and "description" in refused.json()["message"]
    assert (
        ca.post(
            f"/api/v1/menu/manage/items/{inactive.menu_item}/transitions", json={"action": "publish"}
        ).status_code
        == 409
    )  # not READY: cannot skip a step


def test_publication_authority_and_audit(world: World, seeded: dict[str, httpx.Client]) -> None:
    item = new_test_item(world)
    walk_to_validated(seeded, item)
    sign_all(seeded, item)
    assert act(seeded["KITCHEN_MANAGER"], item.version, "activate").status_code == 200

    public = {i["id"] for i in httpx.get(f"{seeded['CENTRAL_ADMIN'].base_url}/api/v1/menu/items").json()}
    assert str(item.menu_item) not in public  # unpublished items are invisible to customers

    for role in ("KITCHEN_MANAGER", "KITCHEN_STAFF", "CUSTOMER", "DELIVERY_AGENT"):
        assert publish_steps(seeded[role], item.menu_item) == (403, 403), role
    other_rm = login(world.user("REGIONAL_MANAGER", region=world.region_b), "management")
    assert publish_steps(other_rm, item.menu_item) == (404, 404)  # outside assigned region, even directly
    other_rm.close()

    assert publish_steps(seeded["REGIONAL_MANAGER"], item.menu_item) == (200, 200)
    public = {i["id"] for i in httpx.get(f"{seeded['CENTRAL_ADMIN'].base_url}/api/v1/menu/items").json()}
    assert str(item.menu_item) in public

    audit = world.db.execute(
        "SELECT from_status, to_status, actor_role, region_id, actor_user_id IS NOT NULL FROM audit.menu_publications "
        "WHERE menu_item_id = %s ORDER BY id",
        (item.menu_item,),
    ).fetchall()
    assert audit == [
        (None, "DRAFT", "SYSTEM", world.region_a, False),
        ("DRAFT", "READY_FOR_PUBLICATION", "REGIONAL_MANAGER", world.region_a, True),
        ("READY_FOR_PUBLICATION", "PUBLISHED", "REGIONAL_MANAGER", world.region_a, True),
    ]


def test_fixture_rows_would_block_a_production_start(world: World) -> None:
    """Leak control 3: with the TEST menu loaded, the startup check names the tables and refuses."""
    url = URL.create(
        "postgresql+psycopg",
        username="app_api",
        password=os.environ["APP_API_PASSWORD"],
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        database=os.environ["POSTGRES_DB"],
    )
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        counts = fixture_counts(conn)
        assert counts["menu_items"] >= 4 and counts["recipe_versions"] >= 4 and counts["ingredients"] >= 6
        with pytest.raises(FixtureRowsPresent, match="menu_items="):
            assert_no_fixtures(conn)
    engine.dispose()


def test_api_cannot_write_fixture_flags(world: World) -> None:
    with (
        psycopg.connect(
            host="127.0.0.1",
            port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
            dbname=os.environ["POSTGRES_DB"],
            user="app_api",
            password=os.environ["APP_API_PASSWORD"],
            autocommit=True,
        ) as api,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        api.execute("UPDATE app.menu_items SET is_test_fixture = false WHERE false")
