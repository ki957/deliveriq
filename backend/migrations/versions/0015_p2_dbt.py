"""P2 dbt run support (Task 12B; DATA_PIPELINE §5, §7, §11, §12; DDR-116 (4), (8), (9), (10), (12)).

- `p2_elt` reads the reference tables the dims need, by column only: no kitchen address or location, and
  never customer, user, address or GPS tables (DDR-116 (4)).
- `ops.dataset_freshness`: written only by the P2 `publish freshness` stage after every critical dbt test
  passed (DDR-116 (8)); read by the API.
- `ops.pipeline_schedules`: the optional P2 timer, off by default, 60 minutes (labelled test default),
  changed by a CA through the API (DDR-116 (9)). `ops.queue_due_schedules()` lets the worker queue a due
  `timer` run without any table grant (as for the delivery sweep, DDR-113 (17)).
- `p2_elt` may read the outbox backlog for the warning check (DDR-116 (12)).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
-- ---------------------------------------------------------------- reference reads for the dims (DDR-116 (4))
GRANT SELECT (id, code, name, status) ON app.regions TO p2_elt;
GRANT SELECT (id, code, region_id, name, status) ON app.kitchens TO p2_elt;
GRANT SELECT (id, name) ON app.menu_categories TO p2_elt;
GRANT SELECT (id, kitchen_id, category_id, name, price_paise, publication_status, is_test_fixture)
    ON app.menu_items TO p2_elt;
GRANT SELECT (id, name, unit, origin) ON app.ingredients TO p2_elt;
GRANT EXECUTE ON FUNCTION ops.outbox_backlog() TO p2_elt;

-- ---------------------------------------------------------------- freshness (DDR-116 (8))
CREATE TABLE ops.dataset_freshness (
    dataset      text PRIMARY KEY CHECK (dataset IN ('analytics', 'analytics_synthetic')),
    fresh_as_of  timestamptz NOT NULL,
    run_id       uuid NOT NULL REFERENCES ops.pipeline_runs (id),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON ops.dataset_freshness TO p2_elt;
GRANT SELECT ON ops.dataset_freshness TO app_api;

-- ---------------------------------------------------------------- schedule (DDR-116 (9))
CREATE TABLE ops.pipeline_schedules (
    pipeline          text PRIMARY KEY REFERENCES ops.pipelines (name),
    enabled           boolean NOT NULL DEFAULT false,
    interval_minutes  integer NOT NULL DEFAULT 60 CHECK (interval_minutes IN (15, 30, 60, 240)),
    -- 60 minutes is a labelled test default (not defined in the sources).
    interval_is_test_default boolean NOT NULL DEFAULT true,
    updated_by        uuid REFERENCES app.users (id) ON DELETE SET NULL,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    reason            text CHECK (char_length(reason) <= 500)
);
INSERT INTO ops.pipeline_schedules (pipeline) VALUES ('p2_elt');
GRANT SELECT ON ops.pipeline_schedules TO app_api;
GRANT UPDATE (enabled, interval_minutes, interval_is_test_default, updated_by, updated_at, reason)
    ON ops.pipeline_schedules TO app_api;

-- The worker's timer: queue one `timer` run for each enabled schedule that is due and has no active run.
CREATE FUNCTION ops.queue_due_schedules() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops AS $$
DECLARE
    s record;
    v_run uuid;
    v_queued integer := 0;
BEGIN
    FOR s IN
        SELECT sc.pipeline, sc.interval_minutes FROM ops.pipeline_schedules sc
         WHERE sc.enabled
           AND NOT EXISTS (SELECT 1 FROM ops.pipeline_runs r
                            WHERE r.pipeline = sc.pipeline AND r.status IN ('queued', 'running'))
           AND COALESCE((SELECT max(r.queued_at) FROM ops.pipeline_runs r WHERE r.pipeline = sc.pipeline),
                        '-infinity'::timestamptz) < now() - make_interval(mins => sc.interval_minutes)
         FOR UPDATE OF sc SKIP LOCKED
    LOOP
        INSERT INTO ops.pipeline_runs (pipeline, trigger, input_ref) VALUES (s.pipeline, 'timer', 'run')
            RETURNING id INTO v_run;
        INSERT INTO ops.job_queue (run_id) VALUES (v_run);
        v_queued := v_queued + 1;
    END LOOP;
    RETURN v_queued;
END $$;
REVOKE ALL ON FUNCTION ops.queue_due_schedules() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.queue_due_schedules() TO worker;
"""

DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS ops.queue_due_schedules();
DROP TABLE IF EXISTS ops.pipeline_schedules;
DROP TABLE IF EXISTS ops.dataset_freshness;
REVOKE EXECUTE ON FUNCTION ops.outbox_backlog() FROM p2_elt;
REVOKE SELECT ON app.ingredients, app.menu_items, app.menu_categories, app.kitchens, app.regions FROM p2_elt;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
