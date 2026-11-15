"""Allow future approval publication and enforce the fixture gate in K2 SQL."""

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE kitchen_rag.chunks DROP CONSTRAINT chunks_status_check;
    ALTER TABLE kitchen_rag.chunks ADD CONSTRAINT chunks_status_check
      CHECK (status IN ('DRAFT', 'PUBLISHED'));
    DROP FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text);
    CREATE FUNCTION kitchen_rag.stage_recipe_draft(
        p_kitchen uuid, p_version uuid, p_doc_version integer, p_section text,
        p_source_ref text, p_content text, p_sha text, p_allow_fixtures boolean
    ) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, kitchen_rag AS $$
    DECLARE fixture_flag boolean;
    BEGIN
      SELECT rv.is_test_fixture INTO fixture_flag
      FROM app.recipe_versions rv JOIN app.recipes r ON r.id = rv.recipe_id
      JOIN kitchen_rag.kitchen_scope ks ON ks.kitchen_id = r.kitchen_id
      WHERE r.kitchen_id = p_kitchen AND rv.id = p_version
        AND (rv.status = 'DRAFT' OR rv.is_test_fixture)
        AND (NOT rv.is_test_fixture OR p_allow_fixtures);
      IF NOT FOUND THEN RAISE EXCEPTION 'recipe version is outside Kitchen scope or fixture policy'; END IF;
      INSERT INTO kitchen_rag.chunks
        (kitchen_id, doc_id, doc_version, section_path, source_ref, audience, visibility,
         status, is_test_fixture, content, content_sha256, recipe_version_id)
      VALUES (p_kitchen, 'recipe:' || p_version::text, p_doc_version, p_section, p_source_ref,
              'KITCHEN', 'ALL', 'DRAFT', fixture_flag, p_content, p_sha, p_version)
      ON CONFLICT (kitchen_id, doc_id, doc_version, section_path) DO NOTHING;
    END $$;
    REVOKE ALL ON FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text,boolean) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text,boolean) TO rag_kitchen;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text,boolean);
    CREATE FUNCTION kitchen_rag.stage_recipe_draft(
        p_kitchen uuid, p_version uuid, p_doc_version integer, p_section text,
        p_source_ref text, p_content text, p_sha text
    ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, app, kitchen_rag AS $$
    DECLARE fixture_flag boolean;
    BEGIN
      SELECT rv.is_test_fixture INTO fixture_flag
      FROM app.recipe_versions rv JOIN app.recipes r ON r.id = rv.recipe_id
      JOIN kitchen_rag.kitchen_scope ks ON ks.kitchen_id = r.kitchen_id
      WHERE r.kitchen_id = p_kitchen AND rv.id = p_version
        AND (rv.status = 'DRAFT' OR rv.is_test_fixture);
      IF NOT FOUND THEN RAISE EXCEPTION 'recipe version is outside Kitchen scope'; END IF;
      INSERT INTO kitchen_rag.chunks
        (kitchen_id, doc_id, doc_version, section_path, source_ref, audience, visibility,
         status, is_test_fixture, content, content_sha256, recipe_version_id)
      VALUES (p_kitchen, 'recipe:' || p_version::text, p_doc_version, p_section, p_source_ref,
              'KITCHEN', 'ALL', 'DRAFT', fixture_flag, p_content, p_sha, p_version)
      ON CONFLICT (kitchen_id, doc_id, doc_version, section_path) DO NOTHING;
    END $$;
    REVOKE ALL ON FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text) TO rag_kitchen;
    ALTER TABLE kitchen_rag.chunks DROP CONSTRAINT chunks_status_check;
    ALTER TABLE kitchen_rag.chunks ADD CONSTRAINT chunks_status_check CHECK (status = 'DRAFT');
    """)
