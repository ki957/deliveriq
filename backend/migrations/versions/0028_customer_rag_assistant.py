"""Task 17: Customer RAG, approval and golden-set isolation."""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE app.knowledge_documents DROP CONSTRAINT IF EXISTS knowledge_documents_portal_check;
    ALTER TABLE app.knowledge_documents ADD CONSTRAINT knowledge_documents_portal_check
        CHECK (portal IN ('KITCHEN', 'CUSTOMER'));

    CREATE SCHEMA IF NOT EXISTS customer_rag;
    CREATE TABLE customer_rag.index_versions (
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
    CREATE UNIQUE INDEX customer_rag_one_published_index
        ON customer_rag.index_versions (published) WHERE published;
    INSERT INTO customer_rag.index_versions
        (embedding_model, dimension, model_hash, status, published)
    VALUES ('sentence-transformers/all-MiniLM-L6-v2', 384,
        '457634dbafdbce3fba6cbd75e31a6f981b12484238715ca5c92bafed56b0fc70',
        'STAGED', false)
    ON CONFLICT (embedding_model, model_hash) DO NOTHING;

    CREATE TABLE customer_rag.chunks (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        doc_id text NOT NULL,
        doc_version integer NOT NULL CHECK (doc_version > 0),
        section_path text NOT NULL,
        source_ref text NOT NULL,
        audience text NOT NULL CHECK (audience = 'CUSTOMER'),
        visibility text NOT NULL CHECK (visibility IN ('PUBLIC', 'AUTHENTICATED')),
        status text NOT NULL CHECK (status IN ('DRAFT', 'PUBLISHED')),
        is_test_fixture boolean NOT NULL DEFAULT false,
        content text NOT NULL,
        content_sha256 text NOT NULL,
        search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
        embedding vector(384),
        embedding_model text,
        embedding_model_hash char(64),
        index_version uuid REFERENCES customer_rag.index_versions(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (doc_id, doc_version, section_path),
        CHECK (embedding IS NULL OR (
            embedding_model = 'sentence-transformers/all-MiniLM-L6-v2'
            AND embedding_model_hash IS NOT NULL AND index_version IS NOT NULL))
    );
    CREATE INDEX customer_rag_chunks_search_idx ON customer_rag.chunks USING gin(search_vector);
    CREATE INDEX customer_rag_chunks_embedding_idx
        ON customer_rag.chunks USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL AND status = 'PUBLISHED';

    ALTER TABLE ops.ai_golden_sets DROP CONSTRAINT IF EXISTS ai_golden_sets_portal_check;
    ALTER TABLE ops.ai_golden_sets ADD CONSTRAINT ai_golden_sets_portal_check
        CHECK (portal IN ('KITCHEN', 'CUSTOMER'));
    ALTER TABLE ops.ai_golden_sets DROP CONSTRAINT IF EXISTS ai_golden_sets_approval_label_check;
    ALTER TABLE ops.ai_golden_sets ADD CONSTRAINT ai_golden_sets_approval_label_check CHECK (
        approval_label IN ('draft, not the DDR-90 golden set',
            'approved DDR-90 Kitchen golden set', 'approved DDR-90 Customer golden set'));
    INSERT INTO ops.ai_golden_sets (suite, portal, name, approval_label, case_count, leak_count, status)
    VALUES ('DDR-90', 'CUSTOMER', 'Customer golden set (awaiting CA approval)',
        'draft, not the DDR-90 golden set', 60, 0, 'DRAFT');

    CREATE FUNCTION customer_rag.stage_draft(
        p_doc_id text, p_display_name text, p_doc_version integer,
        p_source_ref text, p_section text, p_content text, p_sha text,
        p_visibility text
    ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, app, customer_rag AS $$
    DECLARE v_document uuid;
    BEGIN
        INSERT INTO app.knowledge_documents (portal, doc_id, display_name)
        VALUES ('CUSTOMER', p_doc_id, p_display_name)
        ON CONFLICT (doc_id) DO UPDATE SET display_name = EXCLUDED.display_name;
        SELECT id INTO v_document FROM app.knowledge_documents
            WHERE doc_id = p_doc_id AND portal = 'CUSTOMER';
        INSERT INTO app.knowledge_document_versions
            (document_id, doc_version, content, content_sha256, status)
        VALUES (v_document, p_doc_version, p_content, p_sha, 'DRAFT')
        ON CONFLICT (document_id, content_sha256) DO NOTHING;
        INSERT INTO customer_rag.chunks
            (doc_id, doc_version, section_path, source_ref, audience, visibility,
             status, content, content_sha256)
        VALUES (p_doc_id, p_doc_version, p_section, p_source_ref, 'CUSTOMER',
            p_visibility, 'DRAFT', p_content, p_sha)
        ON CONFLICT (doc_id, doc_version, section_path) DO NOTHING;
    END $$;
    REVOKE ALL ON FUNCTION customer_rag.stage_draft(text,text,integer,text,text,text,text,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION customer_rag.stage_draft(text,text,integer,text,text,text,text,text) TO rag_customer;

    CREATE FUNCTION app.retrieve_customer_chunks_hybrid(
        p_question text, p_query_vector vector(384), p_authenticated boolean,
        p_include_fixtures boolean
    ) RETURNS TABLE(id uuid, content text, source_ref text, retrieval_score double precision)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, customer_rag AS $$
    WITH scoped AS (
        SELECT c.* FROM customer_rag.chunks c
        WHERE c.status = 'PUBLISHED' AND c.audience = 'CUSTOMER'
          AND (c.visibility = 'PUBLIC' OR (c.visibility = 'AUTHENTICATED' AND p_authenticated))
          AND (p_include_fixtures OR NOT c.is_test_fixture)
    ), lexical AS (
        SELECT s.id, row_number() OVER (
            ORDER BY ts_rank_cd(s.search_vector, plainto_tsquery('english', p_question)) DESC, s.id
        ) AS rank FROM scoped s
        WHERE s.search_vector @@ plainto_tsquery('english', p_question)
        ORDER BY rank LIMIT 20
    ), semantic AS (
        SELECT s.id, row_number() OVER (ORDER BY s.embedding <=> p_query_vector, s.id) AS rank
        FROM scoped s WHERE p_query_vector IS NOT NULL AND s.embedding IS NOT NULL
        ORDER BY rank LIMIT 20
    ), fused AS (
        SELECT id, sum(1.0 / (60.0 + rank)) AS score FROM (
            SELECT id, rank FROM lexical UNION ALL SELECT id, rank FROM semantic
        ) ranked GROUP BY id
    )
    SELECT s.id, s.content, s.source_ref, f.score
    FROM fused f JOIN scoped s USING (id)
    ORDER BY f.score DESC, s.id LIMIT 6
    $$;
    REVOKE ALL ON FUNCTION app.retrieve_customer_chunks_hybrid(text, vector(384), boolean, boolean) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.retrieve_customer_chunks_hybrid(text, vector(384), boolean, boolean) TO app_api;

    CREATE FUNCTION app.approve_customer_knowledge(
        p_version uuid, p_actor uuid, p_reason text
    ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, app, customer_rag, audit AS $$
    DECLARE v_sha char(64); v_status text;
    BEGIN
        SELECT v.content_sha256, v.status INTO v_sha, v_status
        FROM app.knowledge_document_versions v JOIN app.knowledge_documents d ON d.id = v.document_id
        WHERE v.id = p_version AND d.portal = 'CUSTOMER' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'customer knowledge version not found'; END IF;
        IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'customer knowledge version is not draft'; END IF;
        UPDATE app.knowledge_document_versions SET status='APPROVED', approved_by=p_actor,
            approved_at=now(), decision_reason=p_reason WHERE id=p_version;
        UPDATE customer_rag.chunks SET status='PUBLISHED'
            WHERE content_sha256=v_sha AND status='DRAFT';
        INSERT INTO audit.events (actor_user_id, actor_role, action, target_type, target_id,
            outcome, reason, after_summary)
        VALUES (p_actor, 'CENTRAL_ADMIN', 'knowledge.customer.approve',
            'knowledge_document_version', p_version::text, 'SUCCESS', p_reason,
            jsonb_build_object('status','APPROVED','content_sha256',v_sha));
    END $$;
    REVOKE ALL ON FUNCTION app.approve_customer_knowledge(uuid, uuid, text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.approve_customer_knowledge(uuid, uuid, text) TO app_api;

    CREATE FUNCTION app.reject_customer_knowledge(
        p_version uuid, p_actor uuid, p_reason text
    ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, app, audit AS $$
    DECLARE v_status text;
    BEGIN
        SELECT v.status INTO v_status FROM app.knowledge_document_versions v
            JOIN app.knowledge_documents d ON d.id=v.document_id
            WHERE v.id=p_version AND d.portal='CUSTOMER' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'customer knowledge version not found'; END IF;
        IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'customer knowledge version is not draft'; END IF;
        UPDATE app.knowledge_document_versions SET status='REJECTED', decision_reason=p_reason WHERE id=p_version;
        INSERT INTO audit.events (actor_user_id, actor_role, action, target_type, target_id,
            outcome, reason, after_summary)
        VALUES (p_actor, 'CENTRAL_ADMIN', 'knowledge.customer.reject',
            'knowledge_document_version', p_version::text, 'SUCCESS', p_reason,
            jsonb_build_object('status','REJECTED'));
    END $$;
    REVOKE ALL ON FUNCTION app.reject_customer_knowledge(uuid, uuid, text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.reject_customer_knowledge(uuid, uuid, text) TO app_api;

    CREATE FUNCTION app.approve_customer_golden_set(
        p_set uuid, p_actor uuid, p_reason text
    ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, ops, audit AS $$
    DECLARE v_status text; v_cases integer; v_leaks integer;
    BEGIN
        SELECT status, case_count, leak_count INTO v_status, v_cases, v_leaks
        FROM ops.ai_golden_sets WHERE id=p_set AND portal='CUSTOMER' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'customer golden set not found'; END IF;
        IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'golden set is not draft'; END IF;
        IF v_cases <> 60 THEN RAISE EXCEPTION 'customer golden set must contain 60 cases'; END IF;
        IF v_leaks <> 0 THEN RAISE EXCEPTION 'golden set has scope leaks'; END IF;
        UPDATE ops.ai_golden_sets SET status='APPROVED',
            approval_label='approved DDR-90 Customer golden set', approved_by=p_actor,
            approved_at=now(), decision_reason=p_reason WHERE id=p_set;
        INSERT INTO audit.events (actor_user_id, actor_role, action, target_type, target_id,
            outcome, reason, after_summary)
        VALUES (p_actor, 'CENTRAL_ADMIN', 'knowledge.customer.golden_set_approve',
            'ai_golden_set', p_set::text, 'SUCCESS', p_reason,
            jsonb_build_object('status','APPROVED','case_count',v_cases));
    END $$;
    REVOKE ALL ON FUNCTION app.approve_customer_golden_set(uuid, uuid, text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.approve_customer_golden_set(uuid, uuid, text) TO app_api;

    GRANT SELECT ON customer_rag.index_versions TO app_api;
    GRANT SELECT ON customer_rag.chunks TO app_api;
    GRANT SELECT ON ops.ai_golden_sets TO app_api;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION IF EXISTS app.approve_customer_golden_set(uuid, uuid, text);
    DROP FUNCTION IF EXISTS app.reject_customer_knowledge(uuid, uuid, text);
    DROP FUNCTION IF EXISTS app.approve_customer_knowledge(uuid, uuid, text);
    DROP FUNCTION IF EXISTS app.retrieve_customer_chunks_hybrid(text, vector(384), boolean, boolean);
    DROP FUNCTION IF EXISTS customer_rag.stage_draft(text,text,integer,text,text,text,text,text);
    DROP TABLE IF EXISTS customer_rag.chunks;
    DROP TABLE IF EXISTS customer_rag.index_versions;
    DROP SCHEMA IF EXISTS customer_rag;
    """)
