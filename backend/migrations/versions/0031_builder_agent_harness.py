"""Builder Agent review tasks and DDR-90 golden-set results."""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
ALTER TABLE ops.ai_eval_runs
    ADD COLUMN evaluation_results jsonb NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(evaluation_results) = 'object');

CREATE TABLE ops.builder_agent_proposals (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES app.users(id),
    request        text NOT NULL CHECK (length(request) BETWEEN 1 AND 2000),
    summary        text NOT NULL CHECK (length(summary) BETWEEN 1 AND 1000),
    files          jsonb NOT NULL CHECK (jsonb_typeof(files) = 'array'),
    diff           text NOT NULL CHECK (length(diff) > 0),
    test_result    jsonb NOT NULL CHECK (jsonb_typeof(test_result) = 'object'),
    base_sha       char(40) NOT NULL CHECK (base_sha ~ '^[0-9a-f]{40}$'),
    prompt_sha256  char(64) NOT NULL CHECK (prompt_sha256 ~ '^[0-9a-f]{64}$'),
    status         text NOT NULL DEFAULT 'REVIEW' CHECK (status IN ('REVIEW', 'OPENED')),
    branch_name    text,
    pr_url         text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    opened_at      timestamptz,
    CHECK ((status = 'REVIEW' AND branch_name IS NULL AND pr_url IS NULL)
        OR (status = 'OPENED' AND branch_name IS NOT NULL AND pr_url IS NOT NULL))
);
CREATE INDEX builder_agent_proposals_user_created_idx
    ON ops.builder_agent_proposals (user_id, created_at DESC);
GRANT SELECT, INSERT, UPDATE ON ops.builder_agent_proposals TO app_api;

CREATE FUNCTION ops.record_builder_agent_eval_run(
    p_dataset_hash text, p_runtime_settings jsonb, p_evaluation_results jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops AS $$
DECLARE run_id uuid := gen_random_uuid();
BEGIN
    INSERT INTO ops.ai_eval_runs
        (id, suite, dataset_hash, approval_label, runtime_settings, evaluation_results)
    VALUES (
        run_id, 'DDR-90', p_dataset_hash,
        'draft, not the DDR-90 golden set', p_runtime_settings, p_evaluation_results
    );
    RETURN run_id;
END $$;
REVOKE ALL ON FUNCTION ops.record_builder_agent_eval_run(text, jsonb, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.record_builder_agent_eval_run(text, jsonb, jsonb) TO app_api;
"""

DOWNGRADE_SQL = """
REVOKE EXECUTE ON FUNCTION ops.record_builder_agent_eval_run(text, jsonb, jsonb) FROM app_api;
DROP FUNCTION IF EXISTS ops.record_builder_agent_eval_run(text, jsonb, jsonb);
DROP TABLE IF EXISTS ops.builder_agent_proposals;
ALTER TABLE ops.ai_eval_runs DROP COLUMN IF EXISTS evaluation_results;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
