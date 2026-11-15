"""Task 16C: Kitchen hybrid retrieval, versioned embeddings and KM approval."""

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
CREATE TABLE app.knowledge_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portal text NOT NULL CHECK (portal = 'KITCHEN'),
    doc_id text NOT NULL UNIQUE,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.knowledge_document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES app.knowledge_documents(id) ON DELETE CASCADE,
    doc_version integer NOT NULL CHECK (doc_version > 0),
    content text NOT NULL,
    content_sha256 char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    approved_by uuid REFERENCES app.users(id),
    approved_at timestamptz,
    decision_reason text,
    UNIQUE (document_id, doc_version),
    UNIQUE (document_id, content_sha256),
    CHECK ((status = 'APPROVED') = (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE INDEX knowledge_versions_status_idx
    ON app.knowledge_document_versions (status, submitted_at DESC);

CREATE TABLE kitchen_rag.index_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    embedding_model text NOT NULL,
    dimension integer NOT NULL CHECK (dimension > 0),
    model_hash char(64) NOT NULL CHECK (model_hash ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('STAGED', 'PUBLISHED', 'RETIRED')),
    published boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    UNIQUE (embedding_model, model_hash)
);
CREATE UNIQUE INDEX kitchen_rag_one_published_index
    ON kitchen_rag.index_versions (published) WHERE published;
INSERT INTO kitchen_rag.index_versions
    (embedding_model, dimension, model_hash, status, published)
VALUES
    ('sentence-transformers/all-MiniLM-L6-v2', 384,
     '457634dbafdbce3fba6cbd75e31a6f981b12484238715ca5c92bafed56b0fc70',
     'STAGED', false)
ON CONFLICT (embedding_model, model_hash) DO NOTHING;

CREATE TABLE ops.ai_golden_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    suite text NOT NULL CHECK (suite = 'DDR-90'),
    portal text NOT NULL CHECK (portal = 'KITCHEN'),
    name text NOT NULL,
    approval_label text NOT NULL CHECK (
        approval_label = 'draft, not the DDR-90 golden set'
        OR approval_label = 'approved DDR-90 Kitchen golden set'
    ),
    case_count integer NOT NULL DEFAULT 0 CHECK (case_count >= 0),
    leak_count integer NOT NULL DEFAULT 0 CHECK (leak_count >= 0),
    status text NOT NULL CHECK (status IN ('DRAFT', 'APPROVED', 'BLOCKED')),
    dataset_hash char(64) CHECK (dataset_hash IS NULL OR dataset_hash ~ '^[0-9a-f]{64}$'),
    approved_by uuid REFERENCES app.users(id),
    approved_at timestamptz,
    decision_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'APPROVED') = (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
INSERT INTO ops.ai_golden_sets (suite, portal, name, approval_label, status)
VALUES ('DDR-90', 'KITCHEN', 'Kitchen golden set (awaiting KM approval)',
        'draft, not the DDR-90 golden set', 'DRAFT');

ALTER TABLE kitchen_rag.chunks
    ADD COLUMN embedding vector(384),
    ADD COLUMN embedding_model text,
    ADD COLUMN embedding_model_hash char(64),
    ADD COLUMN index_version uuid REFERENCES kitchen_rag.index_versions(id);
ALTER TABLE kitchen_rag.chunks
    ADD CONSTRAINT chunks_embedding_metadata_check CHECK (
        embedding IS NULL OR (
            embedding_model = 'sentence-transformers/all-MiniLM-L6-v2'
            AND embedding_model_hash IS NOT NULL
            AND index_version IS NOT NULL
        )
    );
CREATE INDEX kitchen_rag_chunks_embedding_idx
    ON kitchen_rag.chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL AND status = 'PUBLISHED';

GRANT SELECT ON app.knowledge_documents, app.knowledge_document_versions TO app_api;
GRANT SELECT, INSERT, UPDATE ON app.knowledge_documents, app.knowledge_document_versions TO rag_kitchen;
GRANT SELECT ON kitchen_rag.index_versions TO app_api, rag_kitchen;
GRANT SELECT ON ops.ai_golden_sets TO app_api;
GRANT UPDATE (embedding, embedding_model, embedding_model_hash, index_version)
    ON kitchen_rag.chunks TO rag_kitchen;

CREATE FUNCTION app.retrieve_kitchen_chunks_hybrid(
    p_question text, p_query_vector vector(384), p_kitchens uuid[],
    p_include_fixtures boolean, p_recipe_version uuid, p_roles text[]
) RETURNS TABLE(id uuid, content text, source_ref text, recipe_version_id uuid, retrieval_score double precision)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, kitchen_rag AS $$
WITH scoped AS (
    SELECT c.*
    FROM kitchen_rag.chunks c
    WHERE c.status = 'PUBLISHED' AND c.audience = 'KITCHEN'
      AND (c.visibility = 'ALL' OR (c.visibility = 'KM' AND 'KITCHEN_MANAGER' = ANY(p_roles)))
      AND c.kitchen_id = ANY(p_kitchens)
      AND (p_include_fixtures OR NOT c.is_test_fixture)
      AND (p_recipe_version IS NULL OR c.recipe_version_id = p_recipe_version)
), lexical AS (
    SELECT s.id, row_number() OVER (
        ORDER BY ts_rank_cd(s.search_vector, plainto_tsquery('english', p_question)) DESC, s.id
    ) AS rank
    FROM scoped s
    WHERE s.search_vector @@ plainto_tsquery('english', p_question)
    ORDER BY rank LIMIT 20
), semantic AS (
    SELECT s.id, row_number() OVER (ORDER BY s.embedding <=> p_query_vector, s.id) AS rank
    FROM scoped s
    WHERE s.embedding IS NOT NULL
    ORDER BY rank LIMIT 20
), fused AS (
    SELECT id, sum(1.0 / (60.0 + rank)) AS score FROM (
        SELECT id, rank FROM lexical
        UNION ALL
        SELECT id, rank FROM semantic
    ) ranked GROUP BY id
)
SELECT s.id, s.content, s.source_ref, s.recipe_version_id, f.score
FROM fused f JOIN scoped s USING (id)
ORDER BY f.score DESC, s.id
LIMIT 6
$$;
REVOKE ALL ON FUNCTION app.retrieve_kitchen_chunks_hybrid(text, vector(384), uuid[], boolean, uuid, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.retrieve_kitchen_chunks_hybrid(text, vector(384), uuid[], boolean, uuid, text[]) TO app_api;

CREATE FUNCTION app.approve_kitchen_knowledge(
    p_version uuid, p_actor uuid, p_kitchen uuid, p_reason text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, kitchen_rag, audit AS $$
DECLARE v_doc text; v_sha char(64); v_status text;
BEGIN
    SELECT d.doc_id, v.content_sha256, v.status INTO v_doc, v_sha, v_status
    FROM app.knowledge_document_versions v
    JOIN app.knowledge_documents d ON d.id = v.document_id
    WHERE v.id = p_version FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'knowledge version not found'; END IF;
    IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'knowledge version is not draft'; END IF;
    UPDATE app.knowledge_document_versions
       SET status = 'APPROVED', approved_by = p_actor, approved_at = now(), decision_reason = p_reason
     WHERE id = p_version;
    UPDATE kitchen_rag.chunks
       SET status = 'PUBLISHED'
     WHERE kitchen_id = p_kitchen AND doc_id = v_doc AND content_sha256 = v_sha AND status = 'DRAFT';
    INSERT INTO audit.events
        (actor_user_id, actor_role, action, target_type, target_id, kitchen_id, outcome, reason, after_summary)
    VALUES
        (p_actor, 'KITCHEN_MANAGER', 'knowledge.approve', 'knowledge_document_version', p_version::text,
         p_kitchen, 'SUCCESS', p_reason, jsonb_build_object('status', 'APPROVED', 'content_sha256', v_sha));
END $$;
REVOKE ALL ON FUNCTION app.approve_kitchen_knowledge(uuid, uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.approve_kitchen_knowledge(uuid, uuid, uuid, text) TO app_api;

CREATE FUNCTION app.reject_kitchen_knowledge(
    p_version uuid, p_actor uuid, p_kitchen uuid, p_reason text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, audit AS $$
DECLARE v_sha char(64); v_status text;
BEGIN
    SELECT content_sha256, status INTO v_sha, v_status
    FROM app.knowledge_document_versions WHERE id = p_version FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'knowledge version not found'; END IF;
    IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'knowledge version is not draft'; END IF;
    UPDATE app.knowledge_document_versions
       SET status = 'REJECTED', decision_reason = p_reason
     WHERE id = p_version;
    INSERT INTO audit.events
        (actor_user_id, actor_role, action, target_type, target_id, kitchen_id, outcome, reason, after_summary)
    VALUES
        (p_actor, 'KITCHEN_MANAGER', 'knowledge.reject', 'knowledge_document_version', p_version::text,
         p_kitchen, 'SUCCESS', p_reason, jsonb_build_object('status', 'REJECTED', 'content_sha256', v_sha));
END $$;
REVOKE ALL ON FUNCTION app.reject_kitchen_knowledge(uuid, uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.reject_kitchen_knowledge(uuid, uuid, uuid, text) TO app_api;

CREATE FUNCTION app.approve_kitchen_golden_set(
    p_set uuid, p_actor uuid, p_reason text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops, audit AS $$
DECLARE v_status text; v_cases integer; v_leaks integer;
BEGIN
    SELECT status, case_count, leak_count INTO v_status, v_cases, v_leaks
    FROM ops.ai_golden_sets WHERE id = p_set FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'golden set not found'; END IF;
    IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'golden set is not draft'; END IF;
    IF v_cases = 0 THEN RAISE EXCEPTION 'golden set has no cases'; END IF;
    IF v_leaks <> 0 THEN RAISE EXCEPTION 'golden set has scope leaks'; END IF;
    UPDATE ops.ai_golden_sets
       SET status = 'APPROVED', approval_label = 'approved DDR-90 Kitchen golden set',
           approved_by = p_actor, approved_at = now(), decision_reason = p_reason
     WHERE id = p_set;
    INSERT INTO audit.events
        (actor_user_id, actor_role, action, target_type, target_id, outcome, reason, after_summary)
    VALUES
        (p_actor, 'KITCHEN_MANAGER', 'knowledge.golden_set_approve', 'ai_golden_set', p_set::text,
         'SUCCESS', p_reason, jsonb_build_object('status', 'APPROVED', 'case_count', v_cases));
END $$;
REVOKE ALL ON FUNCTION app.approve_kitchen_golden_set(uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.approve_kitchen_golden_set(uuid, uuid, text) TO app_api;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION IF EXISTS app.reject_kitchen_knowledge(uuid, uuid, uuid, text);
    DROP FUNCTION IF EXISTS app.approve_kitchen_knowledge(uuid, uuid, uuid, text);
    DROP FUNCTION IF EXISTS app.approve_kitchen_golden_set(uuid, uuid, text);
    DROP FUNCTION IF EXISTS app.retrieve_kitchen_chunks_hybrid(text, vector(384), uuid[], boolean, uuid, text[]);
    DROP INDEX IF EXISTS kitchen_rag_chunks_embedding_idx;
    ALTER TABLE kitchen_rag.chunks
      DROP CONSTRAINT IF EXISTS chunks_embedding_metadata_check,
      DROP COLUMN IF EXISTS index_version,
      DROP COLUMN IF EXISTS embedding_model_hash,
      DROP COLUMN IF EXISTS embedding_model,
      DROP COLUMN IF EXISTS embedding;
    DROP TABLE IF EXISTS kitchen_rag.index_versions;
    DROP TABLE IF EXISTS ops.ai_golden_sets;
    DROP TABLE IF EXISTS app.knowledge_document_versions, app.knowledge_documents;
    """)
