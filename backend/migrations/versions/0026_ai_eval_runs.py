"""Persist DDR-89 benchmark runs and candidate results through the worker definer API."""

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
CREATE TABLE ops.ai_eval_runs (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    suite                  text NOT NULL CHECK (suite = 'DDR-89'),
    dataset_hash           char(64) NOT NULL CHECK (dataset_hash ~ '^[0-9a-f]{64}$'),
    approval_label         text NOT NULL CHECK (
        approval_label = 'approved for benchmark use only; draft, not the DDR-90 golden set'
    ),
    runtime_settings       jsonb NOT NULL CHECK (jsonb_typeof(runtime_settings) = 'object'),
    created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.ai_eval_results (
    run_id                 uuid NOT NULL REFERENCES ops.ai_eval_runs(id) ON DELETE CASCADE,
    candidate              text NOT NULL CHECK (candidate IN (
        'BAAI/bge-small-en-v1.5',
        'intfloat/e5-small-v2',
        'thenlper/gte-small',
        'sentence-transformers/all-MiniLM-L6-v2'
    )),
    pinned_revision        char(40) NOT NULL CHECK (pinned_revision ~ '^[0-9a-f]{40}$'),
    artifact_hash          char(64) NOT NULL CHECK (artifact_hash ~ '^[0-9a-f]{64}$'),
    dimension              integer NOT NULL CHECK (dimension > 0),
    metrics                jsonb NOT NULL CHECK (jsonb_typeof(metrics) = 'object'),
    CHECK (metrics ?& ARRAY[
        'recall_at_5', 'p95_query_embedding_ms', 'steady_state_added_rss_mb',
        'ingestion_batch_peak_vmhwm_mb', 'ingestion_batch_size'
    ]),
    PRIMARY KEY (run_id, candidate),
    CHECK ((metrics ->> 'recall_at_5')::numeric BETWEEN 0 AND 1),
    CHECK ((metrics ->> 'p95_query_embedding_ms')::numeric >= 0),
    CHECK ((metrics ->> 'steady_state_added_rss_mb')::numeric >= 0),
    CHECK ((metrics ->> 'ingestion_batch_peak_vmhwm_mb')::numeric >= 0),
    CHECK ((metrics ->> 'ingestion_batch_size')::integer > 0)
);
CREATE INDEX ops_ai_eval_runs_created_idx ON ops.ai_eval_runs (created_at DESC);

CREATE FUNCTION ops.record_ai_eval_run(
    p_suite text, p_dataset_hash text, p_approval_label text, p_runtime_settings jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops AS $$
DECLARE run_id uuid := gen_random_uuid();
BEGIN
    INSERT INTO ops.ai_eval_runs (id, suite, dataset_hash, approval_label, runtime_settings)
    VALUES (run_id, p_suite, p_dataset_hash, p_approval_label, p_runtime_settings);
    RETURN run_id;
END $$;

CREATE FUNCTION ops.record_ai_eval_result(
    p_run_id uuid, p_candidate text, p_pinned_revision text, p_artifact_hash text,
    p_dimension integer, p_metrics jsonb
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops AS $$
BEGIN
    INSERT INTO ops.ai_eval_results
        (run_id, candidate, pinned_revision, artifact_hash, dimension, metrics)
    VALUES
        (p_run_id, p_candidate, p_pinned_revision, p_artifact_hash, p_dimension, p_metrics);
END $$;

REVOKE ALL ON FUNCTION ops.record_ai_eval_run(text, text, text, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION ops.record_ai_eval_result(uuid, text, text, text, integer, jsonb) FROM PUBLIC;
GRANT USAGE ON SCHEMA ops TO worker;
GRANT EXECUTE ON FUNCTION ops.record_ai_eval_run(text, text, text, jsonb) TO worker;
GRANT EXECUTE ON FUNCTION ops.record_ai_eval_result(uuid, text, text, text, integer, jsonb) TO worker;
"""

DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS ops.record_ai_eval_result(uuid, text, text, text, integer, jsonb);
DROP FUNCTION IF EXISTS ops.record_ai_eval_run(text, text, text, jsonb);
DROP TABLE IF EXISTS ops.ai_eval_results, ops.ai_eval_runs;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
