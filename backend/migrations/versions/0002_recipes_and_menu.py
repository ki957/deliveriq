"""Ingredients, recipes, recipe versions, sign-offs, menu items and the publication audit.

Sources: DDR-09/10/13/50/54 (recipe lifecycle, sign-offs, no SOP activation), #13 release checklist,
DDR-11/31 (menu publication + readiness), DDR-48 (TEST fixtures), KI-17/18/21 (recipe and
ingredient fields), DATA_PIPELINE_DESIGN §6.1 (P1 parsed-card fields and lineage).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECIPE_STATUSES = (
    "DRAFT",
    "PENDING_VALIDATION",
    "VALIDATED",
    "ACTIVE",
    "REJECTED",
    "SUPERSEDED",
    "DISABLED",
    "QUARANTINED_DUPLICATE_CANDIDATE",
)
MENU_STATUSES = ("DRAFT", "READY_FOR_PUBLICATION", "PUBLISHED", "TEMPORARILY_UNAVAILABLE", "RETIRED")
SIGNOFF_TYPES = ("CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER", "PRODUCT_OWNER")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


UPGRADE_SQL = f"""
-- ---------------------------------------------------------------- ingredients (KI-21; stock in Task 8)
CREATE TABLE app.ingredients (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name           text NOT NULL,
    unit           text NOT NULL CHECK (unit IN ('g', 'ml', 'piece')),
    is_active      boolean NOT NULL DEFAULT true,
    source_sha256  char(64),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, unit)
);
-- DATA_PIPELINE §7: no ingredient name is used with two units.
CREATE UNIQUE INDEX ingredients_name_uq ON app.ingredients (lower(name));

-- ---------------------------------------------------------------- recipes
CREATE TABLE app.recipes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kitchen_id      uuid NOT NULL REFERENCES app.kitchens (id),
    -- MENU001..MENU104 for SOP cards; NULL for TEST recipes.
    source_menu_id  text UNIQUE CHECK (source_menu_id ~ '^MENU[0-9]{{3}}$'),
    name            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.recipe_versions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id          uuid NOT NULL REFERENCES app.recipes (id),
    version            integer NOT NULL CHECK (version > 0),
    status             text NOT NULL CHECK (status IN ({_in(RECIPE_STATUSES)})),
    prep_type          text,
    portion            text,
    method             text,
    quality            text,
    inventory_rule     text,
    validation_text    text,
    estimated_prep_minutes integer CHECK (estimated_prep_minutes > 0),
    source_sha256      char(64),
    source_line_start  integer CHECK (source_line_start > 0),
    source_line_end    integer,
    quarantine_reason  text,
    is_test_fixture    boolean NOT NULL DEFAULT false,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (recipe_id, version),
    CHECK (source_line_end IS NULL OR source_line_end >= source_line_start),
    -- Lineage on every real row; TEST fixtures are created from scratch (DDR-48).
    CONSTRAINT recipe_versions_lineage CHECK (is_test_fixture OR source_sha256 IS NOT NULL),
    CONSTRAINT recipe_versions_quarantine_reason
        CHECK (status <> 'QUARANTINED_DUPLICATE_CANDIDATE' OR quarantine_reason IS NOT NULL),
    -- DDR-50: no SOP recipe is ever activated in this POC; only TEST recipes demonstrate activation.
    CONSTRAINT recipe_versions_poc_no_sop_activation CHECK (status <> 'ACTIVE' OR is_test_fixture)
);
-- One ACTIVE version per recipe (DDR-10: a new version supersedes the old).
CREATE UNIQUE INDEX recipe_versions_one_active_uq ON app.recipe_versions (recipe_id) WHERE status = 'ACTIVE';

CREATE TABLE app.recipe_ingredients (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_version_id  uuid NOT NULL REFERENCES app.recipe_versions (id),
    line_no            integer NOT NULL CHECK (line_no > 0),
    ingredient_id      uuid NOT NULL,
    quantity           numeric(12, 3) NOT NULL CHECK (quantity > 0),
    unit               text NOT NULL,
    source_line        integer CHECK (source_line > 0),
    UNIQUE (recipe_version_id, line_no),
    -- The line's unit must be the ingredient's unit.
    FOREIGN KEY (ingredient_id, unit) REFERENCES app.ingredients (id, unit)
);

-- The five #13 release-checklist sign-offs: mandatory audit records, not activation (DDR-10, DDR-54).
CREATE TABLE app.recipe_signoffs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_version_id  uuid NOT NULL REFERENCES app.recipe_versions (id),
    signoff_type       text NOT NULL CHECK (signoff_type IN ({_in(SIGNOFF_TYPES)})),
    signed_by          uuid NOT NULL REFERENCES app.users (id),
    signed_at          timestamptz NOT NULL DEFAULT now(),
    note               text,
    UNIQUE (recipe_version_id, signoff_type)
);

CREATE FUNCTION app.require_five_signoffs() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    IF NEW.status = 'ACTIVE' AND OLD.status IS DISTINCT FROM 'ACTIVE' THEN
        IF (SELECT count(DISTINCT signoff_type) FROM app.recipe_signoffs
             WHERE recipe_version_id = NEW.id) < {len(SIGNOFF_TYPES)} THEN
            RAISE EXCEPTION 'recipe version % cannot be activated without all five sign-offs', NEW.id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Only ACTIVE versions may be pinned to order items (DDR-10); checked in 0003.

-- ---------------------------------------------------------------- menu (DDR-11, CU-06/08)
CREATE TABLE app.menu_categories (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name           text NOT NULL UNIQUE,
    display_order  integer NOT NULL DEFAULT 0
);

CREATE TABLE app.menu_items (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kitchen_id            uuid NOT NULL REFERENCES app.kitchens (id),
    recipe_id             uuid NOT NULL REFERENCES app.recipes (id),
    category_id           uuid REFERENCES app.menu_categories (id),
    name                  text NOT NULL,
    description           text,
    is_veg                boolean,
    spice_level           text,
    -- Integer paise, tax-inclusive (CU-15). No real prices exist (DDR-32).
    price_paise           integer CHECK (price_paise > 0),
    tax_classification    text,
    prep_time_minutes     integer CHECK (prep_time_minutes > 0),
    image_url             text,
    image_is_placeholder  boolean NOT NULL DEFAULT false,
    allergen_info         text,
    allergen_verified     boolean NOT NULL DEFAULT false,
    publication_status    text NOT NULL CHECK (publication_status IN ({_in(MENU_STATUSES)})),
    is_test_fixture       boolean NOT NULL DEFAULT false,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, is_test_fixture),
    -- Allergen data only if verified (DDR-11).
    CHECK (allergen_info IS NULL OR allergen_verified),
    -- DDR-48: fixture names start with "TEST – "; real names never do.
    CONSTRAINT menu_items_test_prefix CHECK (is_test_fixture = (name LIKE 'TEST – %'))
);

-- Readiness checklist (DDR-11) for READY_FOR_PUBLICATION and PUBLISHED; ACTIVE recipe required.
CREATE FUNCTION app.check_menu_readiness() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    missing text[] := ARRAY[]::text[];
BEGIN
    IF NEW.publication_status NOT IN ('READY_FOR_PUBLICATION', 'PUBLISHED') THEN
        RETURN NEW;
    END IF;
    -- array_append, not ||: `text[] || 'literal'` is parsed as an array literal and fails.
    IF NOT EXISTS (SELECT 1 FROM app.recipe_versions v
                    WHERE v.recipe_id = NEW.recipe_id AND v.status = 'ACTIVE') THEN
        missing := array_append(missing, 'active recipe version');
    END IF;
    IF NEW.category_id IS NULL THEN missing := array_append(missing, 'category'); END IF;
    IF NEW.description IS NULL THEN missing := array_append(missing, 'description'); END IF;
    IF NEW.is_veg IS NULL THEN missing := array_append(missing, 'veg flag'); END IF;
    IF NEW.spice_level IS NULL THEN missing := array_append(missing, 'spice level'); END IF;
    IF NEW.price_paise IS NULL THEN missing := array_append(missing, 'price'); END IF;
    IF NEW.tax_classification IS NULL THEN missing := array_append(missing, 'tax classification'); END IF;
    IF NEW.prep_time_minutes IS NULL THEN missing := array_append(missing, 'preparation time'); END IF;
    IF NEW.image_url IS NULL AND NOT NEW.image_is_placeholder THEN
        missing := array_append(missing, 'image');
    END IF;
    IF cardinality(missing) > 0 THEN
        RAISE EXCEPTION 'menu item % is not ready: missing %', NEW.id, array_to_string(missing, ', ')
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Publication audit (DDR-31): actor, role, region, timestamp, menu item, action. Append-only.
CREATE TABLE audit.menu_publications (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_item_id    uuid NOT NULL,
    from_status     text,
    to_status       text NOT NULL,
    actor_user_id   uuid,
    actor_role      text NOT NULL,
    region_id       uuid NOT NULL,
    reason          text,
    correlation_id  text,
    occurred_at     timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION app.audit_menu_publication() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, audit AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.publication_status IS NOT DISTINCT FROM NEW.publication_status THEN
        RETURN NEW;
    END IF;
    INSERT INTO audit.menu_publications (menu_item_id, from_status, to_status, actor_user_id, actor_role,
                                         region_id, reason, correlation_id)
    SELECT NEW.id,
           CASE WHEN TG_OP = 'UPDATE' THEN OLD.publication_status END,
           NEW.publication_status,
           nullif(current_setting('app.actor_user_id', true), '')::uuid,
           current_setting('app.actor_role', true),
           k.region_id,
           nullif(current_setting('app.reason', true), ''),
           nullif(current_setting('app.correlation_id', true), '')
      FROM app.kitchens k WHERE k.id = NEW.kitchen_id;
    RETURN NEW;
END $$;

-- Triggers fire in name order: transition check (a_) → readiness (b_) → sign-offs (b_) → audit (AFTER).
CREATE TRIGGER a_recipe_versions_transition BEFORE INSERT OR UPDATE OF status ON app.recipe_versions
    FOR EACH ROW EXECUTE FUNCTION app.enforce_status_transition('recipe', 'status');
CREATE TRIGGER b_recipe_versions_signoffs BEFORE UPDATE OF status ON app.recipe_versions
    FOR EACH ROW EXECUTE FUNCTION app.require_five_signoffs();
CREATE TRIGGER recipe_versions_touch BEFORE UPDATE ON app.recipe_versions
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();

CREATE TRIGGER a_menu_items_transition BEFORE INSERT OR UPDATE OF publication_status ON app.menu_items
    FOR EACH ROW EXECUTE FUNCTION app.enforce_status_transition('menu', 'publication_status');
CREATE TRIGGER b_menu_items_readiness BEFORE INSERT OR UPDATE ON app.menu_items
    FOR EACH ROW EXECUTE FUNCTION app.check_menu_readiness();
CREATE TRIGGER menu_items_touch BEFORE UPDATE ON app.menu_items
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER z_menu_items_audit AFTER INSERT OR UPDATE OF publication_status ON app.menu_items
    FOR EACH ROW EXECUTE FUNCTION app.audit_menu_publication();
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS audit.menu_publications;
DROP TABLE IF EXISTS app.menu_items;
DROP TABLE IF EXISTS app.menu_categories;
DROP TABLE IF EXISTS app.recipe_signoffs;
DROP TABLE IF EXISTS app.recipe_ingredients;
DROP TABLE IF EXISTS app.recipe_versions;
DROP TABLE IF EXISTS app.recipes;
DROP TABLE IF EXISTS app.ingredients;
DROP FUNCTION IF EXISTS app.audit_menu_publication();
DROP FUNCTION IF EXISTS app.check_menu_readiness();
DROP FUNCTION IF EXISTS app.require_five_signoffs();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
