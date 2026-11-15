"""Remove inherited table-wide K2 writes that could change fixture provenance."""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    REVOKE INSERT, UPDATE ON kitchen_rag.chunks FROM rag_kitchen;
    GRANT INSERT (kitchen_id, doc_id, doc_version, section_path, source_ref, audience, visibility,
                  status, content, content_sha256, recipe_version_id)
      ON kitchen_rag.chunks TO rag_kitchen;
    GRANT UPDATE (content, content_sha256) ON kitchen_rag.chunks TO rag_kitchen;
    """)


def downgrade() -> None:
    op.execute("""
    REVOKE INSERT, UPDATE ON kitchen_rag.chunks FROM rag_kitchen;
    GRANT INSERT, UPDATE ON kitchen_rag.chunks TO rag_kitchen;
    """)
