"""Expose scoped recipe rows for K2 and derive fixture provenance in SQL."""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION kitchen_rag.recipe_draft_sources(p_allow_fixtures boolean)
    RETURNS TABLE(kitchen_id uuid, recipe_version_id uuid, recipe_name text, version integer,
                  status text, is_test_fixture boolean, portion text, method text,
                  quality text, inventory_rule text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, app, kitchen_rag AS $$
      SELECT r.kitchen_id, rv.id, r.name, rv.version, rv.status, rv.is_test_fixture,
             rv.portion, rv.method, rv.quality, rv.inventory_rule
      FROM app.recipe_versions rv JOIN app.recipes r ON r.id = rv.recipe_id
      JOIN kitchen_rag.kitchen_scope ks ON ks.kitchen_id = r.kitchen_id
      WHERE (rv.is_test_fixture AND p_allow_fixtures)
         OR (NOT rv.is_test_fixture AND rv.status = 'DRAFT')
      ORDER BY r.kitchen_id, rv.id
    $$;
    REVOKE ALL ON FUNCTION kitchen_rag.recipe_draft_sources(boolean) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION kitchen_rag.recipe_draft_sources(boolean) TO rag_kitchen;
    CREATE FUNCTION kitchen_rag.stage_recipe_draft(
        p_kitchen uuid, p_version uuid, p_doc_version integer, p_section text,
        p_source_ref text, p_content text, p_sha text
    ) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app, kitchen_rag AS $$
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
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION kitchen_rag.stage_recipe_draft(uuid,uuid,integer,text,text,text,text);
    DROP FUNCTION kitchen_rag.recipe_draft_sources(boolean);
    """)
