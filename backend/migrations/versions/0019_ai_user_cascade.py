"""Cascade AI metadata and conversations when a user is removed (DDR-119)."""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE ops.ai_requests DROP CONSTRAINT ai_requests_user_id_fkey;
    ALTER TABLE ops.ai_requests ADD CONSTRAINT ai_requests_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES app.users(id) ON DELETE CASCADE;
    ALTER TABLE app.ai_conversations DROP CONSTRAINT ai_conversations_user_id_fkey;
    ALTER TABLE app.ai_conversations ADD CONSTRAINT ai_conversations_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES app.users(id) ON DELETE CASCADE;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE ops.ai_requests DROP CONSTRAINT ai_requests_user_id_fkey;
    ALTER TABLE ops.ai_requests ADD CONSTRAINT ai_requests_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES app.users(id);
    ALTER TABLE app.ai_conversations DROP CONSTRAINT ai_conversations_user_id_fkey;
    ALTER TABLE app.ai_conversations ADD CONSTRAINT ai_conversations_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES app.users(id);
    """)
