"""Production-safe seeds and least-privilege grants for every DB role.

Seeds contain no fixture rows: one region, the labelled synthetic kitchen fixture (DDR-39), config
values from #15 §6-7 and the plan, and the pipeline registry. Users, TEST dishes and opening stock are
test fixtures loaded by the fixture loader (local/test only), never by migrations.

Grants follow DOCKER_DEPLOYMENT_DESIGN §6.3 and DDR-63: each pipeline role writes only its targets;
`is_test_fixture` is never insertable or updatable by runtime roles (plan §5.2 control 1).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, value, unit, scope, is_test_default, source)
CONFIG: tuple[tuple[str, str, str, str, bool, str], ...] = (
    ("SERVICEABILITY_STRAIGHT_LINE_MAX", "4", "km", "KITCHEN", False, "#15 §6; CU-03"),
    ("SERVICEABILITY_ROAD_DISTANCE_MAX", "6", "km", "KITCHEN", False, "#15 §6; CU-03"),
    ("MINIMUM_FOOD_SUBTOTAL", "50000", "paise", "KITCHEN", False, "#15 §6; CU-12 (Rs 500)"),
    (
        "DELIVERY_FEE_FLAT",
        "3000",
        "paise",
        "KITCHEN",
        False,
        "DDR-38 (Rs 30 flat, no free-delivery threshold)",
    ),
    ("MAX_CONCURRENT_ORDERS", "10", "orders", "KITCHEN", True, "#15 §7 test value; DDR-42 open"),
    ("CUSTOMER_UNAVAILABLE_WAIT", "5", "minutes", "REGION", False, "DDR-14; #15 §6"),
    ("AGENT_ASSIGNMENT_RESPONSE_TIMEOUT", "60", "seconds", "REGION", False, "#15 §6; DL-04"),
    ("GPS_UPDATE_INTERVAL_MIN", "3", "seconds", "REGION", False, "#15 §6; DL-G1 (DDR-43 interval open)"),
    ("GPS_UPDATE_INTERVAL_MAX", "5", "seconds", "REGION", False, "#15 §6; DL-G1 (DDR-43 interval open)"),
    ("SPECIAL_INSTRUCTIONS_MAX_CHARS", "250", "characters", "GLOBAL", False, "DDR-07; CU-09"),
    ("GPS_RETENTION_DAYS", "30", "days", "GLOBAL", False, "DDR-43"),
)

# (name, display, group, db_role, heavy)
PIPELINES: tuple[tuple[str, str, str, str, bool], ...] = (
    ("p1_sop", "P1 SOP master-data ETL", "DATA", "p1_sop", False),
    ("p2_elt", "P2 operational ELT", "DATA", "p2_elt", True),
    ("p3_synthetic", "P3 synthetic data", "DATA", "p3_synth", True),
    ("k1_customer", "K1 Customer knowledge", "KNOWLEDGE", "rag_customer", True),
    ("k2_kitchen", "K2 Kitchen knowledge", "KNOWLEDGE", "rag_kitchen", True),
    ("k3_management", "K3 Management knowledge", "KNOWLEDGE", "rag_management", True),
)

PIPELINE_ROLES = ("p1_sop", "p2_elt", "p3_synth", "rag_customer", "rag_kitchen", "rag_management")
FIXTURE_TABLES = ("menu_items", "recipe_versions", "orders", "order_items", "payments")


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _config_rows() -> str:
    rows = []
    for key, value, unit, scope, test, src in CONFIG:
        region = "(SELECT id FROM app.regions WHERE code = 'REG-CHN-001')" if scope == "REGION" else "NULL"
        kitchen = "(SELECT id FROM app.kitchens WHERE code = 'KIT-CHN-001')" if scope == "KITCHEN" else "NULL"
        rows.append(
            f"({_literal(key)}, {value}, {_literal(unit)}, {_literal(scope)}, {region}, {kitchen}, "
            f"{str(test).lower()}, {_literal(src)})"
        )
    return ",\n".join(rows)


PIPELINE_ROWS = ",\n".join(
    f"({_literal(n)}, {_literal(d)}, {_literal(g)}, {_literal(r)}, {str(h).lower()})"
    for n, d, g, r, h in PIPELINES
)

SEED_SQL = f"""
INSERT INTO app.regions (code, name, city, state, country, timezone, status)
VALUES ('REG-CHN-001', 'Chennai', 'Chennai', 'Tamil Nadu', 'India', 'Asia/Kolkata', 'ACTIVE');

-- #15 §3 synthetic test address and coordinates; flagged synthetic (DDR-39).
INSERT INTO app.kitchens (code, region_id, name, address, location, location_is_synthetic, mode, status)
SELECT 'KIT-CHN-001', r.id, 'DeliverIQ Chennai POC Kitchen',
       'Synthetic Test Address, Chennai, Tamil Nadu, India',
       ST_SetSRID(ST_MakePoint(80.2707, 13.0827), 4326)::geography, true, 'NORMAL', 'ACTIVE'
  FROM app.regions r WHERE r.code = 'REG-CHN-001';

INSERT INTO app.config_settings (key, value, unit, scope_type, region_id, kitchen_id, is_test_default, source_ref)
VALUES {_config_rows()};

INSERT INTO ops.pipelines (name, display_name, pipeline_group, db_role, is_heavy) VALUES {PIPELINE_ROWS};
"""

GRANT_SQL = f"""
-- ---------------------------------------------------------------- schema usage
GRANT USAGE ON SCHEMA app, audit, ops TO app_api;
GRANT USAGE ON SCHEMA app, staging, ops TO p1_sop;
GRANT USAGE ON SCHEMA app, raw, staging, analytics, ops TO p2_elt;
GRANT USAGE ON SCHEMA app, synthetic, analytics_synthetic, ops TO p3_synth;
GRANT USAGE ON SCHEMA customer_rag, ops TO rag_customer;
GRANT USAGE ON SCHEMA kitchen_rag, ops TO rag_kitchen;
GRANT USAGE ON SCHEMA management_rag, ops TO rag_management;
-- dbt builds its own models (DDR-63): P2 in staging/analytics, P3 in analytics_synthetic.
GRANT CREATE ON SCHEMA staging, analytics TO p2_elt;
GRANT CREATE ON SCHEMA analytics_synthetic TO p3_synth;

-- ---------------------------------------------------------------- app_api (API runtime)
GRANT SELECT ON ALL TABLES IN SCHEMA app TO app_api;
GRANT INSERT, UPDATE ON app.regions, app.kitchens, app.config_settings, app.users, app.role_assignments,
    app.ingredients, app.recipes, app.recipe_ingredients, app.menu_categories, app.delivery_assignments TO app_api;
GRANT INSERT ON app.recipe_signoffs, app.outbox TO app_api;
GRANT INSERT, SELECT ON audit.events TO app_api;
GRANT SELECT ON audit.menu_publications TO app_api;
GRANT SELECT ON ALL TABLES IN SCHEMA ops TO app_api;
GRANT INSERT (pipeline, trigger, actor_user_id, is_test, region_id, input_ref, retry_of),
      UPDATE (cancel_requested) ON ops.pipeline_runs TO app_api;
GRANT INSERT (run_id) ON ops.job_queue TO app_api;

-- Fixture tables: every column except is_test_fixture (and id) is writable by app_api.
DO $grants$
DECLARE
    t     text;
    cols  text;
BEGIN
    FOREACH t IN ARRAY ARRAY[{", ".join(_literal(t) for t in FIXTURE_TABLES)}] LOOP
        SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
          FROM information_schema.columns
         WHERE table_schema = 'app' AND table_name = t AND column_name NOT IN ('id', 'is_test_fixture');
        EXECUTE format('GRANT INSERT (%s), UPDATE (%s) ON app.%I TO app_api', cols, cols, t);
    END LOOP;
END $grants$;

-- ---------------------------------------------------------------- pipeline roles: ops run records
GRANT SELECT ON ops.pipelines TO {", ".join(PIPELINE_ROLES)};
GRANT SELECT, INSERT, UPDATE ON ops.pipeline_runs, ops.pipeline_stage_runs TO {", ".join(PIPELINE_ROLES)};
GRANT SELECT, INSERT ON ops.ingestion_errors, ops.dq_results TO {", ".join(PIPELINE_ROLES)};
GRANT SELECT, INSERT ON ops.source_registry TO p1_sop;

-- ---------------------------------------------------------------- P1: SOP master data (DRAFT only, DDR-09)
GRANT SELECT ON app.kitchens, app.ingredients, app.recipes, app.recipe_versions, app.recipe_ingredients TO p1_sop;
GRANT INSERT, UPDATE ON app.ingredients, app.recipes, app.recipe_ingredients TO p1_sop;
DO $p1$
DECLARE
    cols text;
BEGIN
    SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
      FROM information_schema.columns
     WHERE table_schema = 'app' AND table_name = 'recipe_versions'
       AND column_name NOT IN ('id', 'is_test_fixture');
    EXECUTE format('GRANT INSERT (%s), UPDATE (%s) ON app.recipe_versions TO p1_sop', cols, cols);
END $p1$;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA staging
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO p1_sop;

-- ---------------------------------------------------------------- P2: outbox → raw → dbt
GRANT SELECT, UPDATE (published_at, attempts, last_error) ON app.outbox TO p2_elt;
GRANT SELECT, INSERT ON raw.events TO p2_elt;

-- ---------------------------------------------------------------- P3: synthetic (TEST dishes only)
GRANT SELECT ON app.menu_items TO p3_synth;
GRANT SELECT, INSERT ON synthetic.events TO p3_synth;

-- ---------------------------------------------------------------- RAG roles: own schema only (ADR-009)
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA customer_rag
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_customer;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA kitchen_rag
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_kitchen;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA management_rag
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_management;
"""

REVOKE_SQL = f"""
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA staging REVOKE ALL ON TABLES FROM p1_sop;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA customer_rag REVOKE ALL ON TABLES FROM rag_customer;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA kitchen_rag REVOKE ALL ON TABLES FROM rag_kitchen;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA management_rag REVOKE ALL ON TABLES FROM rag_management;
REVOKE ALL ON ALL TABLES IN SCHEMA app, audit, ops, raw, synthetic
    FROM app_api, {", ".join(PIPELINE_ROLES)};
REVOKE ALL ON SCHEMA app, audit, ops, raw, staging, analytics, synthetic, analytics_synthetic,
    customer_rag, kitchen_rag, management_rag FROM app_api, {", ".join(PIPELINE_ROLES)};
DELETE FROM ops.pipelines;
DELETE FROM app.config_settings;
DELETE FROM app.kitchens;
DELETE FROM app.regions;
"""


def upgrade() -> None:
    op.execute(SEED_SQL)
    op.execute(GRANT_SQL)


def downgrade() -> None:
    op.execute(REVOKE_SQL)
