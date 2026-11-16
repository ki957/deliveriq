"""Task 17B: persist Customer Prompt Guard events and Customer golden-set evaluations."""

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
CREATE TABLE ops.prompt_guard_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES app.users(id),
    harness text NOT NULL CHECK (harness = 'customer_assistant'),
    outcome text NOT NULL CHECK (outcome IN ('off', 'clear', 'blocked', 'unavailable')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ops_prompt_guard_events_created_idx ON ops.prompt_guard_events (created_at DESC);
GRANT SELECT, INSERT ON ops.prompt_guard_events TO app_api;
REVOKE ALL ON ALL TABLES IN SCHEMA app, audit, ops, kitchen_rag, management_rag FROM rag_customer;
GRANT SELECT ON customer_rag.index_versions, customer_rag.chunks TO rag_customer;

ALTER TABLE ops.ai_eval_runs DROP CONSTRAINT ai_eval_runs_suite_check;
ALTER TABLE ops.ai_eval_runs ADD CONSTRAINT ai_eval_runs_suite_check
    CHECK (suite IN ('DDR-89', 'DDR-90'));
ALTER TABLE ops.ai_eval_runs DROP CONSTRAINT ai_eval_runs_approval_label_check;
ALTER TABLE ops.ai_eval_runs ADD CONSTRAINT ai_eval_runs_approval_label_check
    CHECK (approval_label IN (
        'approved for benchmark use only; draft, not the DDR-90 golden set',
        'draft, not the DDR-90 golden set'
    ));

ALTER TABLE ops.ai_eval_results DROP CONSTRAINT ai_eval_results_candidate_check;
ALTER TABLE ops.ai_eval_results DROP CONSTRAINT ai_eval_results_dimension_check;
ALTER TABLE ops.ai_eval_results ALTER COLUMN dimension DROP NOT NULL;
ALTER TABLE ops.ai_eval_results ALTER COLUMN pinned_revision DROP NOT NULL;
ALTER TABLE ops.ai_eval_results ALTER COLUMN artifact_hash DROP NOT NULL;
ALTER TABLE ops.ai_eval_results ADD COLUMN evaluation_kind text NOT NULL DEFAULT 'embedding_benchmark'
    CHECK (evaluation_kind IN ('embedding_benchmark', 'customer_golden'));
ALTER TABLE ops.ai_eval_results ADD COLUMN code_sha256 char(64)
    CHECK (code_sha256 IS NULL OR code_sha256 ~ '^[0-9a-f]{64}$');

DO $$
DECLARE constraint_row record;
BEGIN
    FOR constraint_row IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'ops.ai_eval_results'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ~ '(recall_at_5|p95_query_embedding_ms|steady_state_added_rss_mb|ingestion_batch_peak_vmhwm_mb|ingestion_batch_size)'
    LOOP
        EXECUTE format('ALTER TABLE ops.ai_eval_results DROP CONSTRAINT %I', constraint_row.conname);
    END LOOP;
END $$;
ALTER TABLE ops.ai_eval_results ADD CONSTRAINT ai_eval_results_candidate_check CHECK (
    (evaluation_kind = 'embedding_benchmark' AND candidate IN (
        'BAAI/bge-small-en-v1.5', 'intfloat/e5-small-v2', 'thenlper/gte-small',
        'sentence-transformers/all-MiniLM-L6-v2'
    )) OR (evaluation_kind = 'customer_golden' AND candidate = 'mock/customer_assistant')
);
ALTER TABLE ops.ai_eval_results ADD CONSTRAINT ai_eval_results_dimension_check CHECK (
    (evaluation_kind = 'embedding_benchmark' AND dimension > 0
        AND pinned_revision IS NOT NULL AND artifact_hash IS NOT NULL)
    OR (evaluation_kind = 'customer_golden' AND dimension IS NULL
        AND pinned_revision IS NULL AND artifact_hash IS NULL AND code_sha256 IS NOT NULL)
);
ALTER TABLE ops.ai_eval_results ADD CONSTRAINT ai_eval_results_metrics_shape_check CHECK (
    (evaluation_kind = 'embedding_benchmark' AND metrics ?& ARRAY[
        'recall_at_5', 'p95_query_embedding_ms', 'steady_state_added_rss_mb',
        'ingestion_batch_peak_vmhwm_mb', 'ingestion_batch_size'
    ] AND (metrics ->> 'recall_at_5')::numeric BETWEEN 0 AND 1
        AND (metrics ->> 'p95_query_embedding_ms')::numeric >= 0
        AND (metrics ->> 'steady_state_added_rss_mb')::numeric >= 0
        AND (metrics ->> 'ingestion_batch_peak_vmhwm_mb')::numeric >= 0
        AND (metrics ->> 'ingestion_batch_size')::integer > 0)
    OR (evaluation_kind = 'customer_golden' AND metrics ?& ARRAY[
        'case_count', 'answerable_count', 'must_refuse_count',
        'cross_customer_leak_count', 'injection_count', 'leak_count'
    ] AND (metrics ->> 'case_count')::integer = 60
        AND (metrics ->> 'leak_count')::integer >= 0)
);

"""

DOWNGRADE_SQL = """
ALTER TABLE ops.ai_eval_results DROP CONSTRAINT IF EXISTS ai_eval_results_metrics_shape_check;
ALTER TABLE ops.ai_eval_results DROP CONSTRAINT IF EXISTS ai_eval_results_candidate_check;
ALTER TABLE ops.ai_eval_results DROP CONSTRAINT IF EXISTS ai_eval_results_dimension_check;
ALTER TABLE ops.ai_eval_results DROP COLUMN IF EXISTS code_sha256;
ALTER TABLE ops.ai_eval_results DROP COLUMN IF EXISTS evaluation_kind;
ALTER TABLE ops.ai_eval_results ALTER COLUMN dimension SET NOT NULL;
ALTER TABLE ops.ai_eval_results ALTER COLUMN pinned_revision SET NOT NULL;
ALTER TABLE ops.ai_eval_results ALTER COLUMN artifact_hash SET NOT NULL;
ALTER TABLE ops.ai_eval_results ADD CONSTRAINT ai_eval_results_candidate_check CHECK (candidate IN (
    'BAAI/bge-small-en-v1.5', 'intfloat/e5-small-v2', 'thenlper/gte-small',
    'sentence-transformers/all-MiniLM-L6-v2'
));
ALTER TABLE ops.ai_eval_results ADD CONSTRAINT ai_eval_results_dimension_check CHECK (dimension > 0);
ALTER TABLE ops.ai_eval_runs DROP CONSTRAINT IF EXISTS ai_eval_runs_suite_check;
ALTER TABLE ops.ai_eval_runs ADD CONSTRAINT ai_eval_runs_suite_check CHECK (suite = 'DDR-89');
ALTER TABLE ops.ai_eval_runs DROP CONSTRAINT IF EXISTS ai_eval_runs_approval_label_check;
ALTER TABLE ops.ai_eval_runs ADD CONSTRAINT ai_eval_runs_approval_label_check
    CHECK (approval_label = 'approved for benchmark use only; draft, not the DDR-90 golden set');
REVOKE SELECT ON customer_rag.index_versions, customer_rag.chunks FROM rag_customer;
DROP TABLE IF EXISTS ops.prompt_guard_events;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
