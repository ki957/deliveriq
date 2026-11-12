"""Worker grants, cancel function, P1 staging, SOP lineage columns and the recipe review queue.

Sources: DDR-63/67 (framework, operating rules), DDR-102–DDR-105 (P1 parsing, review queue, lineage,
fault injection, worker), KITCHEN_SOURCE_VALIDATION §7 and §9 (staging, traceability).
Requires the `worker` role (created by the Postgres init script; `make db-roles` adds it to existing
volumes before migrations run).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_REASONS = "'MISSING_BATCH_RECIPE', 'COMPOSITE_INGREDIENT', 'AMBIGUOUS_INGREDIENT'"

UPGRADE_SQL = f"""
DO $check$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'worker') THEN
        RAISE EXCEPTION 'role "worker" is missing: run `make db-roles` (or `make up`) before migrating';
    END IF;
END $check$;

-- ---------------------------------------------------------------- SOP lineage (KITCHEN_SOURCE_VALIDATION §9)
ALTER TABLE app.recipe_versions
    ADD COLUMN source_path         text,
    ADD COLUMN source_card_id      text,
    ADD COLUMN source_page_ref     integer CHECK (source_page_ref > 0),
    -- Footer category: unconfirmed source attribute only (DDR-36, DDR-102).
    ADD COLUMN candidate_category  text,
    ADD COLUMN import_run_id       uuid REFERENCES ops.pipeline_runs (id),
    ADD COLUMN imported_at         timestamptz;

ALTER TABLE app.recipe_ingredients
    ADD COLUMN original_text  text,
    ADD COLUMN source_sha256  char(64);

ALTER TABLE app.ingredients
    ADD COLUMN origin text NOT NULL DEFAULT 'MANUAL' CHECK (origin IN ('SOP_DERIVED', 'TEST_FIXTURE', 'MANUAL'));

-- P1 writes lineage once; no role may edit it afterwards (§9: no in-place edits after import).
-- `id` too: P1 inserts deterministic uuid5 IDs so re-runs add nothing (DDR-103); never UPDATE (id).
GRANT INSERT (id, source_path, source_card_id, source_page_ref, candidate_category, import_run_id, imported_at)
    ON app.recipe_versions TO p1_sop;

-- ---------------------------------------------------------------- P1 staging (per run; never read by portals)
CREATE TABLE staging.sop_cards (
    run_id              uuid NOT NULL REFERENCES ops.pipeline_runs (id),
    source_line_start   integer NOT NULL,
    source_line_end     integer NOT NULL,
    card_id             text NOT NULL,
    name                text NOT NULL,
    status              text NOT NULL CHECK (status IN ('VALID', 'DUPLICATE_CANDIDATE', 'REJECTED')),
    fields              jsonb NOT NULL,
    page_ref            integer,
    candidate_category  text,
    PRIMARY KEY (run_id, source_line_start)
);

CREATE TABLE staging.sop_ingredient_lines (
    run_id         uuid NOT NULL REFERENCES ops.pipeline_runs (id),
    source_line    integer NOT NULL,
    card_line      integer NOT NULL,
    line_no        integer NOT NULL,
    original_text  text NOT NULL,
    name           text NOT NULL,
    quantity       numeric(12, 3),
    unit           text,
    problem        text,
    PRIMARY KEY (run_id, source_line),
    FOREIGN KEY (run_id, card_line) REFERENCES staging.sop_cards (run_id, source_line_start)
);

-- ---------------------------------------------------------------- review queue (DDR-103)
CREATE TABLE app.recipe_review_items (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_version_id  uuid NOT NULL REFERENCES app.recipe_versions (id),
    reason_code        text NOT NULL CHECK (reason_code IN ({REVIEW_REASONS})),
    subject            text NOT NULL,
    detail             text NOT NULL,
    source_ref         text NOT NULL,
    source_line        integer,
    status             text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED')),
    acknowledged_by    uuid REFERENCES app.users (id),
    acknowledged_at    timestamptz,
    note               text,
    import_run_id      uuid REFERENCES ops.pipeline_runs (id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (recipe_version_id, reason_code, subject),
    CHECK ((status = 'OPEN') = (acknowledged_by IS NULL)),
    CHECK (status = 'OPEN' OR (note IS NOT NULL AND acknowledged_at IS NOT NULL))
);
CREATE INDEX recipe_review_items_open_idx ON app.recipe_review_items (recipe_version_id) WHERE status = 'OPEN';

-- A recipe with open review items cannot be submitted for validation (DDR-103).
CREATE FUNCTION app.block_submit_with_open_review() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    IF NEW.status = 'PENDING_VALIDATION' AND OLD.status IS DISTINCT FROM 'PENDING_VALIDATION'
       AND EXISTS (SELECT 1 FROM app.recipe_review_items r
                    WHERE r.recipe_version_id = NEW.id AND r.status = 'OPEN') THEN
        RAISE EXCEPTION 'recipe version % has open review items', NEW.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER b_recipe_versions_open_review BEFORE UPDATE OF status ON app.recipe_versions
    FOR EACH ROW EXECUTE FUNCTION app.block_submit_with_open_review();

-- ---------------------------------------------------------------- framework additions (DDR-105)
ALTER TABLE ops.pipeline_runs
    ADD COLUMN report_md      text,
    ADD COLUMN failure_class  text CHECK (failure_class IN ('transient', 'data', 'structural'));

CREATE TABLE ops.workers (
    worker_id       text PRIMARY KEY,
    started_at      timestamptz NOT NULL DEFAULT now(),
    heartbeat_at    timestamptz NOT NULL DEFAULT now(),
    current_run_id  uuid REFERENCES ops.pipeline_runs (id)
);

-- Queued runs are cancelled at once; running ones are asked to stop at the next stage boundary.
CREATE FUNCTION ops.cancel_run(p_run uuid) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops AS $$
BEGIN
    UPDATE ops.pipeline_runs SET status = 'cancelled', started_at = coalesce(started_at, now()),
           finished_at = now(), error_summary = 'Cancelled before start'
     WHERE id = p_run AND status = 'queued';
    IF FOUND THEN
        RETURN 'cancelled';
    END IF;
    UPDATE ops.pipeline_runs SET cancel_requested = true WHERE id = p_run AND status = 'running';
    IF FOUND THEN
        RETURN 'cancel_requested';
    END IF;
    RETURN 'not_active';
END $$;
REVOKE ALL ON FUNCTION ops.cancel_run(uuid) FROM PUBLIC;

-- ---------------------------------------------------------------- grants
GRANT USAGE ON SCHEMA ops TO worker;
GRANT SELECT ON ops.pipelines TO worker;
GRANT SELECT, UPDATE (status, started_at, finished_at, error_summary, failure_class) ON ops.pipeline_runs TO worker;
GRANT SELECT, UPDATE ON ops.job_queue TO worker;
GRANT SELECT, INSERT, UPDATE ON ops.workers TO worker;

GRANT EXECUTE ON FUNCTION ops.cancel_run(uuid) TO app_api;
GRANT SELECT ON ops.workers TO app_api;
GRANT SELECT ON app.recipe_review_items TO app_api;
GRANT UPDATE (status, acknowledged_by, acknowledged_at, note) ON app.recipe_review_items TO app_api;

GRANT SELECT, INSERT ON app.recipe_review_items TO p1_sop;
"""

DOWNGRADE_SQL = """
REVOKE INSERT (id) ON app.recipe_versions FROM p1_sop;
DROP FUNCTION IF EXISTS ops.cancel_run(uuid);
DROP TABLE IF EXISTS ops.workers;
ALTER TABLE ops.pipeline_runs DROP COLUMN IF EXISTS failure_class, DROP COLUMN IF EXISTS report_md;
DROP TRIGGER IF EXISTS b_recipe_versions_open_review ON app.recipe_versions;
DROP FUNCTION IF EXISTS app.block_submit_with_open_review();
DROP TABLE IF EXISTS app.recipe_review_items;
DROP TABLE IF EXISTS staging.sop_ingredient_lines;
DROP TABLE IF EXISTS staging.sop_cards;
ALTER TABLE app.ingredients DROP COLUMN IF EXISTS origin;
ALTER TABLE app.recipe_ingredients DROP COLUMN IF EXISTS source_sha256, DROP COLUMN IF EXISTS original_text;
ALTER TABLE app.recipe_versions
    DROP COLUMN IF EXISTS imported_at, DROP COLUMN IF EXISTS import_run_id,
    DROP COLUMN IF EXISTS candidate_category, DROP COLUMN IF EXISTS source_page_ref,
    DROP COLUMN IF EXISTS source_card_id, DROP COLUMN IF EXISTS source_path;
REVOKE ALL ON ALL TABLES IN SCHEMA ops FROM worker;
REVOKE ALL ON SCHEMA ops FROM worker;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
