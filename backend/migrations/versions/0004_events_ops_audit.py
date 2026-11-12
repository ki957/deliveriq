"""Outbox, raw and synthetic event landing, pipeline-runs framework tables and the audit log.

Sources: ADR-004 / DATA_PIPELINE_DESIGN §6.2 (event envelope), §6.5 (run record), §10 (rejected raw
events kept), DDR-63/64/67 (framework, permissions, operating rules), DDR-74 (synthetic path),
Phase 2 §11.3 and PL-12 (audit fields, append-only).

The job-queue claim path and its worker role are added with the worker in Task 5.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENVELOPE_COLUMNS = """
    event_id        uuid        NOT NULL,
    event_type      text        NOT NULL CHECK (event_type ~ '^[a-z_]+\\.[a-z_]+$'),
    event_version   integer     NOT NULL CHECK (event_version > 0),
    occurred_at     timestamptz NOT NULL,
    aggregate_type  text        NOT NULL,
    aggregate_id    uuid        NOT NULL,
    region_id       uuid,
    kitchen_id      uuid,
    correlation_id  text,
    idempotency_key text        NOT NULL,
    data            jsonb       NOT NULL DEFAULT '{}'::jsonb
"""

UPGRADE_SQL = f"""
-- ---------------------------------------------------------------- outbox (same transaction as the change)
CREATE TABLE app.outbox (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    {ENVELOPE_COLUMNS.strip()},
    is_test_fixture  boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    published_at     timestamptz,
    attempts         integer NOT NULL DEFAULT 0,
    last_error       text,
    UNIQUE (event_id),
    UNIQUE (event_type, idempotency_key)
);
CREATE INDEX outbox_unpublished_idx ON app.outbox (id) WHERE published_at IS NULL;

-- ---------------------------------------------------------------- raw landing: append-only (DDR-78)
CREATE TABLE raw.events (
    {ENVELOPE_COLUMNS.strip()},
    is_test_fixture  boolean NOT NULL,
    landed_at        timestamptz NOT NULL DEFAULT now(),
    parse_status     text NOT NULL DEFAULT 'accepted' CHECK (parse_status IN ('accepted', 'rejected')),
    parse_error      text,
    PRIMARY KEY (event_id),
    CHECK (parse_status = 'accepted' OR parse_error IS NOT NULL)
);

-- Simulated events (P3). A separate schema, never mixed into raw (DDR-74).
CREATE TABLE synthetic.events (
    {ENVELOPE_COLUMNS.strip()},
    generator_seed   bigint NOT NULL,
    pipeline_run_id  uuid   NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id)
);

-- ---------------------------------------------------------------- pipeline-runs framework (DDR-63)
CREATE TABLE ops.pipelines (
    name          text PRIMARY KEY CHECK (name ~ '^[a-z][a-z0-9_]+$'),
    display_name  text NOT NULL,
    pipeline_group text NOT NULL CHECK (pipeline_group IN ('DATA', 'KNOWLEDGE', 'MAINTENANCE')),
    db_role       text NOT NULL,
    is_heavy      boolean NOT NULL DEFAULT false
);

CREATE TABLE ops.pipeline_runs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline          text NOT NULL REFERENCES ops.pipelines (name),
    trigger           text NOT NULL CHECK (trigger IN ('ui', 'cli', 'timer')),
    actor_user_id     uuid,
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'succeeded', 'completed_with_quarantine',
                                        'failed', 'cancelled')),
    is_test           boolean NOT NULL DEFAULT false,
    region_id         uuid,
    input_ref         text,
    counts            jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    error_summary     text,
    code_version      text,
    cancel_requested  boolean NOT NULL DEFAULT false,
    retry_of          uuid REFERENCES ops.pipeline_runs (id),
    queued_at         timestamptz NOT NULL DEFAULT now(),
    started_at        timestamptz,
    finished_at       timestamptz,
    CHECK (finished_at IS NULL OR started_at IS NOT NULL),
    CHECK (status NOT IN ('succeeded', 'completed_with_quarantine', 'failed') OR finished_at IS NOT NULL)
);
-- DDR-67 rule 5: one active run per pipeline.
CREATE UNIQUE INDEX pipeline_runs_one_active_uq ON ops.pipeline_runs (pipeline)
    WHERE status IN ('queued', 'running');
CREATE INDEX pipeline_runs_history_idx ON ops.pipeline_runs (pipeline, queued_at DESC);

CREATE TABLE ops.pipeline_stage_runs (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id         uuid NOT NULL REFERENCES ops.pipeline_runs (id),
    seq            integer NOT NULL CHECK (seq > 0),
    stage          text NOT NULL,
    status         text NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped',
                                                   'cancelled')),
    rows_in        integer CHECK (rows_in >= 0),
    rows_out       integer CHECK (rows_out >= 0),
    rows_rejected  integer CHECK (rows_rejected >= 0),
    detail         jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    started_at     timestamptz,
    finished_at    timestamptz,
    UNIQUE (run_id, seq)
);

CREATE TABLE ops.ingestion_errors (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id       uuid NOT NULL REFERENCES ops.pipeline_runs (id),
    stage        text NOT NULL,
    record_ref   text,
    reason_code  text NOT NULL,
    message      text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.dq_results (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      uuid NOT NULL REFERENCES ops.pipeline_runs (id),
    check_name  text NOT NULL,
    severity    text NOT NULL CHECK (severity IN ('critical', 'warning')),
    status      text NOT NULL CHECK (status IN ('pass', 'fail', 'error', 'skipped')),
    failures    integer NOT NULL DEFAULT 0 CHECK (failures >= 0),
    detail      jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.source_registry (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id           uuid REFERENCES ops.pipeline_runs (id),
    source_path      text NOT NULL,
    expected_sha256  char(64),
    observed_sha256  char(64),
    size_bytes       bigint CHECK (size_bytes >= 0),
    line_count       integer CHECK (line_count >= 0),
    status           text NOT NULL CHECK (status IN ('OK', 'MISSING', 'HASH_MISMATCH', 'METADATA_MISMATCH',
                                                     'UNEXPECTED')),
    checked_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.job_queue (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        uuid NOT NULL UNIQUE REFERENCES ops.pipeline_runs (id),
    available_at  timestamptz NOT NULL DEFAULT now(),
    claimed_by    text,
    claimed_at    timestamptz,
    heartbeat_at  timestamptz,
    attempts      integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts  integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    last_error    text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_queue_ready_idx ON ops.job_queue (available_at) WHERE claimed_at IS NULL;

-- ---------------------------------------------------------------- audit log (PL-12, Phase 2 §11.3)
CREATE TABLE audit.events (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    actor_user_id   uuid,
    actor_role      text NOT NULL,
    action          text NOT NULL,
    target_type     text NOT NULL,
    target_id       text,
    region_id       uuid,
    kitchen_id      uuid,
    outcome         text NOT NULL CHECK (outcome IN ('SUCCESS', 'DENIED', 'FAILED')),
    reason          text,
    correlation_id  text,
    before_summary  jsonb,
    after_summary   jsonb
);
CREATE INDEX audit_events_scope_idx ON audit.events (region_id, occurred_at DESC);

-- Append-only for everyone, including the owner: corrections are new rows.
CREATE FUNCTION audit.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit.events
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();
CREATE TRIGGER menu_publications_append_only BEFORE UPDATE OR DELETE ON audit.menu_publications
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();
CREATE TRIGGER status_history_append_only BEFORE UPDATE OR DELETE ON app.status_history
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();
CREATE TRIGGER raw_events_append_only BEFORE UPDATE OR DELETE ON raw.events
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();
CREATE TRIGGER recipe_signoffs_append_only BEFORE UPDATE OR DELETE ON app.recipe_signoffs
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutation();
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS raw_events_append_only ON raw.events;
DROP TRIGGER IF EXISTS recipe_signoffs_append_only ON app.recipe_signoffs;
DROP TRIGGER IF EXISTS status_history_append_only ON app.status_history;
DROP TRIGGER IF EXISTS menu_publications_append_only ON audit.menu_publications;
DROP TABLE IF EXISTS audit.events;
DROP FUNCTION IF EXISTS audit.reject_mutation();
DROP TABLE IF EXISTS ops.job_queue;
DROP TABLE IF EXISTS ops.source_registry;
DROP TABLE IF EXISTS ops.dq_results;
DROP TABLE IF EXISTS ops.ingestion_errors;
DROP TABLE IF EXISTS ops.pipeline_stage_runs;
DROP TABLE IF EXISTS ops.pipeline_runs;
DROP TABLE IF EXISTS ops.pipelines;
DROP TABLE IF EXISTS synthetic.events;
DROP TABLE IF EXISTS raw.events;
DROP TABLE IF EXISTS app.outbox;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
