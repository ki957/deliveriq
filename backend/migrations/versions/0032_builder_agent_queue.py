"""Task queue polled by the host-side Builder Agent runner."""

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
ALTER TABLE ops.builder_agent_proposals
    ADD COLUMN logical_model text NOT NULL DEFAULT 'strong' CHECK (logical_model = 'strong');

CREATE TABLE ops.builder_agent_jobs (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES app.users(id),
    request        text NOT NULL CHECK (length(request) BETWEEN 1 AND 2000),
    state          text NOT NULL DEFAULT 'QUEUED'
                   CHECK (state IN (
                       'QUEUED', 'PROCESSING', 'REVIEW', 'CONFIRM_REQUESTED', 'PUBLISHING', 'OPENED', 'FAILED'
                   )),
    error_message  text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX builder_agent_jobs_queue_idx ON ops.builder_agent_jobs (state, created_at);
GRANT SELECT, INSERT, UPDATE ON ops.builder_agent_jobs TO app_api;
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ops.builder_agent_jobs;
ALTER TABLE ops.builder_agent_proposals DROP COLUMN IF EXISTS logical_model;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
