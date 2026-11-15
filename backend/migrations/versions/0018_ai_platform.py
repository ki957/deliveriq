"""AI gateway routing, request metadata and conversation memory (DDR-119)."""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE ops.ai_routing_overrides (
        harness text PRIMARY KEY,
        logical_model text NOT NULL,
        updated_by uuid NOT NULL REFERENCES app.users(id),
        updated_at timestamptz NOT NULL DEFAULT now(),
        reason text NOT NULL
    );
    CREATE TABLE ops.ai_requests (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id uuid NOT NULL REFERENCES app.users(id),
        harness text NOT NULL,
        logical_model text NOT NULL,
        outcome text NOT NULL,
        latency_ms integer,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE app.ai_conversations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id uuid NOT NULL REFERENCES app.users(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        deleted_at timestamptz
    );
    CREATE TABLE app.ai_messages (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id uuid NOT NULL REFERENCES app.ai_conversations(id) ON DELETE CASCADE,
        role text NOT NULL CHECK (role IN ('user', 'assistant')),
        content text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ops_ai_requests_created_idx ON ops.ai_requests (created_at);
    CREATE INDEX ops_ai_messages_conversation_idx ON app.ai_messages (conversation_id, created_at);
    GRANT SELECT, INSERT, UPDATE ON ops.ai_routing_overrides TO app_api;
    GRANT SELECT, INSERT ON ops.ai_requests TO app_api;
    GRANT SELECT, INSERT, UPDATE ON app.ai_conversations TO app_api;
    GRANT SELECT, INSERT, UPDATE, DELETE ON app.ai_messages TO app_api;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE app.ai_messages, app.ai_conversations, ops.ai_requests, ops.ai_routing_overrides;
    """)
