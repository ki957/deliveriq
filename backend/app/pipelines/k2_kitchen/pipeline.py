"""K2 Kitchen knowledge staging. It records only DRAFT chunks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.pipelines.framework.context import DataError, RunContext
from app.pipelines.framework.registry import register

KNOWLEDGE_DIR = Path(__file__).parents[4] / "knowledge" / "kitchen"
SOURCE_PATTERN = "<!-- status: DRAFT -->"


@register("k2_kitchen")
def run_k2(ctx: RunContext) -> None:
    files = sorted(path for path in KNOWLEDGE_DIR.glob("*.md") if path.name != "README.md")
    with ctx.stage("register_and_stage_drafts") as counts:
        counts.rows_in = len(files)
        staged = 0
        for path in files:
            content = path.read_text(encoding="utf-8")
            if SOURCE_PATTERN not in content:
                raise DataError(f"{path.name} is missing the required DRAFT marker")
            digest = hashlib.sha256(content.encode()).hexdigest()
            ctx.data.execute(
                text("""
                INSERT INTO kitchen_rag.chunks
                    (kitchen_id, doc_id, doc_version, section_path, source_ref, audience, visibility,
                     status, content, content_sha256)
                SELECT k.kitchen_id, :doc_id, 1, 'DRAFT', 'pending KM approval', 'KITCHEN',
                       'ALL', 'DRAFT', :content, :digest
                FROM kitchen_rag.kitchen_scope k
                ON CONFLICT (kitchen_id, doc_id, doc_version, section_path) DO NOTHING
            """),
                {"doc_id": path.stem, "content": content, "digest": digest},
            )
            staged += 1
        allow_fixtures = get_settings().app_env in {"local", "test", "demo"}
        recipe_rows = ctx.data.execute(
            text("SELECT * FROM kitchen_rag.recipe_draft_sources(:allow_fixtures)"),
            {"allow_fixtures": allow_fixtures},
        ).all()
        for recipe in recipe_rows:
            sections = {
                "header": f"{recipe.recipe_name} — DRAFT – not validated ({recipe.status})",
                "portion": recipe.portion,
                "method": recipe.method,
                "quality": recipe.quality,
                "inventory_rule": recipe.inventory_rule,
            }
            for section, content in sections.items():
                if not content or not str(content).strip():
                    continue
                source_ref = f"recipe_version:{recipe.recipe_version_id}#{section}"
                digest = hashlib.sha256(f"{source_ref}\n{content}".encode()).hexdigest()
                ctx.data.execute(
                    text("""
                        SELECT kitchen_rag.stage_recipe_draft(
                            :kitchen, :version, :doc_version, :section,
                            :source_ref, :content, :digest, :allow_fixtures
                        )
                    """),
                    {
                        "kitchen": recipe.kitchen_id,
                        "version": recipe.recipe_version_id,
                        "doc_version": recipe.version,
                        "section": section,
                        "source_ref": source_ref,
                        "content": str(content),
                        "digest": digest,
                        "allow_fixtures": allow_fixtures,
                    },
                )
                staged += 1
        counts.rows_out = staged
        counts.detail["published"] = 0
        ctx.counts.update(
            {
                "documents_seen": len(files),
                "recipe_versions_seen": len(recipe_rows),
                "draft_chunks_staged": staged,
                "test_fixture_versions_seen": sum(bool(recipe.is_test_fixture) for recipe in recipe_rows),
                "published": 0,
            }
        )
