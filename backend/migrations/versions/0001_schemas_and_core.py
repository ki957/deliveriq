"""Schemas, status-transition engine, regions, kitchens, config, users and role assignments.

Sources: DDR-25 (schemas), DDR-17 / Matrix §7 (status machines), DDR-10 (actor + reason on every
transition), #15 §2-4 and §6 (region, kitchen, roles), Phase 2 §6.3 (modelling rules).

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = (
    "app",
    "raw",
    "staging",
    "analytics",
    "synthetic",
    "analytics_synthetic",
    "ops",
    "audit",
    "customer_rag",
    "kitchen_rag",
    "management_rag",
)

ROLES = (
    "CUSTOMER",
    "DELIVERY_AGENT",
    "KITCHEN_STAFF",
    "KITCHEN_MANAGER",
    "REGIONAL_MANAGER",
    "CENTRAL_ADMIN",
)

UPGRADE_SQL = f"""
{"".join(f"CREATE SCHEMA {s};" for s in SCHEMAS)}

-- ---------------------------------------------------------------- transition engine
-- One row per allowed transition. allowed_roles is set only where a DDR names the authority;
-- NULL means the backend service decides (role/scope checks live there).
CREATE TABLE app.status_transitions (
    machine          text    NOT NULL,
    from_status      text    NOT NULL,
    to_status        text    NOT NULL,
    reason_required  boolean NOT NULL DEFAULT false,
    allowed_roles    text[],
    source_ref       text    NOT NULL,
    PRIMARY KEY (machine, from_status, to_status)
);

CREATE TABLE app.status_initial (
    machine     text NOT NULL,
    status      text NOT NULL,
    source_ref  text NOT NULL,
    PRIMARY KEY (machine, status)
);

-- Immutable history of every status change (DDR-10, Phase 2 §6.3 "immutable history").
CREATE TABLE app.status_history (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    machine         text        NOT NULL,
    entity_id       uuid        NOT NULL,
    from_status     text,
    to_status       text        NOT NULL,
    actor_user_id   uuid,
    actor_role      text        NOT NULL CHECK (actor_role IN ({", ".join(f"'{r}'" for r in ROLES)}, 'SYSTEM')),
    reason          text,
    correlation_id  text,
    changed_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (actor_role = 'SYSTEM' OR actor_user_id IS NOT NULL)
);
CREATE INDEX status_history_entity_idx ON app.status_history (machine, entity_id, changed_at);

-- Validates every INSERT/UPDATE of a status column against the tables above and records history.
-- Actor context comes from transaction-local settings set by the backend service:
--   app.actor_role, app.actor_user_id, app.reason, app.correlation_id
-- SECURITY DEFINER so runtime roles cannot write history rows directly.
CREATE FUNCTION app.enforce_status_transition() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
    v_machine   text := TG_ARGV[0];
    v_column    text := TG_ARGV[1];
    v_old       text;
    v_new       text := to_jsonb(NEW) ->> v_column;
    v_role      text := nullif(current_setting('app.actor_role', true), '');
    v_actor     text := nullif(current_setting('app.actor_user_id', true), '');
    v_reason    text := nullif(current_setting('app.reason', true), '');
    v_needs     boolean := false;
    v_allowed   text[];
BEGIN
    IF TG_OP = 'UPDATE' THEN
        v_old := to_jsonb(OLD) ->> v_column;
        IF v_old IS NOT DISTINCT FROM v_new THEN
            RETURN NEW;
        END IF;
        SELECT t.reason_required, t.allowed_roles INTO v_needs, v_allowed
          FROM app.status_transitions t
         WHERE t.machine = v_machine AND t.from_status = v_old AND t.to_status = v_new;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'illegal % transition: % -> %', v_machine, v_old, v_new
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NOT EXISTS (SELECT 1 FROM app.status_initial i WHERE i.machine = v_machine AND i.status = v_new) THEN
        RAISE EXCEPTION 'illegal initial % status: %', v_machine, v_new USING ERRCODE = 'check_violation';
    END IF;

    IF v_role IS NULL THEN
        RAISE EXCEPTION '% status change requires app.actor_role', v_machine USING ERRCODE = 'check_violation';
    END IF;
    IF v_role <> 'SYSTEM' AND v_actor IS NULL THEN
        RAISE EXCEPTION '% status change by % requires app.actor_user_id', v_machine, v_role
            USING ERRCODE = 'check_violation';
    END IF;
    IF v_allowed IS NOT NULL AND NOT (v_role = ANY (v_allowed)) THEN
        RAISE EXCEPTION 'role % may not perform % transition % -> %', v_role, v_machine, v_old, v_new
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF v_needs AND v_reason IS NULL THEN
        RAISE EXCEPTION '% transition % -> % requires a reason', v_machine, v_old, v_new
            USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO app.status_history (machine, entity_id, from_status, to_status, actor_user_id, actor_role,
                                    reason, correlation_id)
    VALUES (v_machine, NEW.id, v_old, v_new, v_actor::uuid, v_role, v_reason,
            nullif(current_setting('app.correlation_id', true), ''));
    RETURN NEW;
END $$;

CREATE FUNCTION app.touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------- regions and kitchens (#15 §2-3)
CREATE TABLE app.regions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code        text NOT NULL UNIQUE CHECK (code ~ '^REG-[A-Z]{{3}}-[0-9]{{3}}$'),
    name        text NOT NULL,
    city        text NOT NULL,
    state       text NOT NULL,
    country     text NOT NULL,
    timezone    text NOT NULL,
    status      text NOT NULL CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.kitchens (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code                   text NOT NULL UNIQUE CHECK (code ~ '^KIT-[A-Z]{{3}}-[0-9]{{3}}$'),
    region_id              uuid NOT NULL REFERENCES app.regions (id),
    name                   text NOT NULL,
    address                text NOT NULL,
    location               geography(Point, 4326) NOT NULL,
    -- DDR-39: no real kitchen location exists; the seeded one is a labelled synthetic fixture.
    location_is_synthetic  boolean NOT NULL,
    mode                   text NOT NULL DEFAULT 'NORMAL' CHECK (mode IN ('NORMAL', 'BUSY', 'PAUSED')),
    status                 text NOT NULL CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, region_id)
);

-- ---------------------------------------------------------------- configuration (#15 §6-7, DDR-14/38/07/43)
CREATE TABLE app.config_settings (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key              text    NOT NULL CHECK (key ~ '^[A-Z][A-Z0-9_]+$'),
    value            numeric NOT NULL,
    unit             text    NOT NULL,
    scope_type       text    NOT NULL CHECK (scope_type IN ('GLOBAL', 'REGION', 'KITCHEN')),
    region_id        uuid REFERENCES app.regions (id),
    kitchen_id       uuid REFERENCES app.kitchens (id),
    -- True when the value is a labelled test default, not an approved operational value.
    is_test_default  boolean NOT NULL DEFAULT false,
    source_ref       text    NOT NULL,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (scope_type = 'GLOBAL'  AND region_id IS NULL AND kitchen_id IS NULL) OR
        (scope_type = 'REGION'  AND region_id IS NOT NULL AND kitchen_id IS NULL) OR
        (scope_type = 'KITCHEN' AND kitchen_id IS NOT NULL AND region_id IS NULL)
    )
);
CREATE UNIQUE INDEX config_settings_scope_uq
    ON app.config_settings (key, scope_type, coalesce(region_id, kitchen_id, '00000000-0000-0000-0000-000000000000'));

-- ---------------------------------------------------------------- identity spine (PL-03, #15 §4)
-- Sessions, OTP challenges and trusted devices are added in Task 4.
CREATE TABLE app.users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name  text NOT NULL,
    mobile_e164   text NOT NULL UNIQUE CHECK (mobile_e164 ~ '^\\+[1-9][0-9]{{7,14}}$'),
    status        text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DEACTIVATED')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Multiple explicit roles per user (PL-03); scope columns per #15 §4.1.
CREATE TABLE app.role_assignments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES app.users (id),
    role        text NOT NULL CHECK (role IN ({", ".join(f"'{r}'" for r in ROLES)})),
    region_id   uuid REFERENCES app.regions (id),
    kitchen_id  uuid REFERENCES app.kitchens (id),
    granted_by  uuid REFERENCES app.users (id),
    granted_at  timestamptz NOT NULL DEFAULT now(),
    revoked_at  timestamptz,
    CHECK (
        (role IN ('CUSTOMER', 'CENTRAL_ADMIN') AND region_id IS NULL AND kitchen_id IS NULL) OR
        (role = 'REGIONAL_MANAGER' AND region_id IS NOT NULL AND kitchen_id IS NULL) OR
        (role IN ('KITCHEN_STAFF', 'KITCHEN_MANAGER') AND region_id IS NOT NULL AND kitchen_id IS NOT NULL) OR
        (role = 'DELIVERY_AGENT' AND region_id IS NOT NULL)
    ),
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);
CREATE UNIQUE INDEX role_assignments_active_uq
    ON app.role_assignments (
        user_id, role,
        coalesce(region_id, '00000000-0000-0000-0000-000000000000'),
        coalesce(kitchen_id, '00000000-0000-0000-0000-000000000000')
    ) WHERE revoked_at IS NULL;

CREATE TRIGGER regions_touch BEFORE UPDATE ON app.regions FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER kitchens_touch BEFORE UPDATE ON app.kitchens FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER users_touch BEFORE UPDATE ON app.users FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER config_touch BEFORE UPDATE ON app.config_settings
    FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("".join(f"DROP SCHEMA IF EXISTS {s} CASCADE;" for s in reversed(SCHEMAS)))
