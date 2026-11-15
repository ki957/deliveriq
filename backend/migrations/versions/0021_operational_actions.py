"""Confirmed Management Operational Actions (DDR-69, DDR-120)."""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE ops.ai_requests ADD COLUMN prompt_sha256 text;
    CREATE TABLE ops.action_proposals (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
        action text NOT NULL,
        arguments jsonb NOT NULL,
        before_state jsonb NOT NULL,
        exact_change jsonb NOT NULL,
        status text NOT NULL DEFAULT 'PROPOSED'
            CHECK (status IN ('PROPOSED', 'EXECUTING', 'COMPLETED')),
        idempotency_key uuid,
        payload_hash text,
        result jsonb,
        created_at timestamptz NOT NULL DEFAULT now(),
        completed_at timestamptz
    );
    CREATE UNIQUE INDEX action_proposal_key_uq ON ops.action_proposals (user_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL;
    GRANT SELECT, INSERT, UPDATE ON ops.action_proposals TO app_api;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE ops.action_proposals; ALTER TABLE ops.ai_requests DROP COLUMN prompt_sha256")
