"""Move AI conversation memory into the approved app schema (DDR-119)."""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE ops.ai_conversations SET SCHEMA app;
    ALTER TABLE ops.ai_messages SET SCHEMA app;
    GRANT SELECT, INSERT, UPDATE ON app.ai_conversations TO app_api;
    GRANT SELECT, INSERT, UPDATE, DELETE ON app.ai_messages TO app_api;
    """)


def downgrade() -> None:
    op.execute("""
    REVOKE ALL ON app.ai_messages, app.ai_conversations FROM app_api;
    ALTER TABLE app.ai_messages SET SCHEMA ops;
    ALTER TABLE app.ai_conversations SET SCHEMA ops;
    """)
