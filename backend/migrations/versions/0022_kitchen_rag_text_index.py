"""Kitchen RAG text index; vector columns follow the owner-approved benchmark."""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE kitchen_rag.kitchen_scope (kitchen_id uuid PRIMARY KEY);
    INSERT INTO kitchen_rag.kitchen_scope SELECT id FROM app.kitchens WHERE status = 'ACTIVE';
    GRANT SELECT ON kitchen_rag.kitchen_scope TO rag_kitchen;
    CREATE TABLE kitchen_rag.chunks (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        kitchen_id uuid NOT NULL REFERENCES kitchen_rag.kitchen_scope(kitchen_id),
        doc_id text NOT NULL,
        doc_version integer NOT NULL CHECK (doc_version > 0),
        section_path text NOT NULL,
        source_ref text NOT NULL,
        audience text NOT NULL CHECK (audience = 'KITCHEN'),
        visibility text NOT NULL CHECK (visibility IN ('ALL', 'KM')),
        status text NOT NULL CHECK (status IN ('DRAFT', 'PUBLISHED')),
        is_test_fixture boolean NOT NULL DEFAULT false,
        content text NOT NULL,
        content_sha256 text NOT NULL,
        recipe_version_id uuid,
        search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (kitchen_id, doc_id, doc_version, section_path)
    );
    CREATE INDEX kitchen_rag_chunks_search_idx ON kitchen_rag.chunks USING gin(search_vector);
    CREATE INDEX kitchen_rag_chunks_scope_idx ON kitchen_rag.chunks(kitchen_id, status, audience);
    REVOKE INSERT, UPDATE ON kitchen_rag.chunks FROM rag_kitchen;
    GRANT SELECT, DELETE ON kitchen_rag.chunks TO rag_kitchen;
    GRANT INSERT (kitchen_id, doc_id, doc_version, section_path, source_ref, audience, visibility, status, content, content_sha256, recipe_version_id) ON kitchen_rag.chunks TO rag_kitchen;
    GRANT UPDATE (content, content_sha256) ON kitchen_rag.chunks TO rag_kitchen;
    CREATE FUNCTION app.retrieve_kitchen_chunks(
        p_question text, p_kitchens uuid[], p_include_fixtures boolean, p_recipe_version uuid, p_roles text[]
    ) RETURNS TABLE(id uuid, content text, source_ref text, recipe_version_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, kitchen_rag AS $$
        SELECT c.id, c.content, c.source_ref, c.recipe_version_id
        FROM kitchen_rag.chunks c
        WHERE c.status = 'PUBLISHED' AND c.audience = 'KITCHEN'
          AND (c.visibility = 'ALL' OR (c.visibility = 'KM' AND 'KITCHEN_MANAGER' = ANY(p_roles)))
          AND c.kitchen_id = ANY(p_kitchens)
          AND (p_include_fixtures OR NOT c.is_test_fixture)
          AND (p_recipe_version IS NULL OR c.recipe_version_id = p_recipe_version)
          AND c.search_vector @@ plainto_tsquery('english', p_question)
        ORDER BY ts_rank_cd(c.search_vector, plainto_tsquery('english', p_question)) DESC, c.id
        LIMIT 6
    $$;
    REVOKE ALL ON FUNCTION app.retrieve_kitchen_chunks(text, uuid[], boolean, uuid, text[]) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.retrieve_kitchen_chunks(text, uuid[], boolean, uuid, text[]) TO app_api;
    CREATE FUNCTION app.kitchen_rag_fixture_count() RETURNS bigint
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, kitchen_rag AS
      $$ SELECT count(*) FROM kitchen_rag.chunks WHERE is_test_fixture $$;
    REVOKE ALL ON FUNCTION app.kitchen_rag_fixture_count() FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.kitchen_rag_fixture_count() TO app_api;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION app.kitchen_rag_fixture_count();
    DROP FUNCTION app.retrieve_kitchen_chunks(text, uuid[], boolean, uuid, text[]);
    DROP TABLE kitchen_rag.chunks;
    DROP TABLE kitchen_rag.kitchen_scope;
    """)
