"""K1 Customer knowledge staging. It records only DRAFT chunks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import text

from app.pipelines.framework.context import DataError, RunContext
from app.pipelines.framework.registry import register

KNOWLEDGE_DIR = Path(__file__).parents[4] / "knowledge" / "customer"
SOURCE_PATTERN = "<!-- status: DRAFT -->"


@register("k1_customer")
def run_k1(ctx: RunContext) -> None:
    files = sorted(path for path in KNOWLEDGE_DIR.glob("*.md") if path.name != "README.md")
    with ctx.stage("register_and_stage_customer_drafts") as counts:
        counts.rows_in = len(files)
        staged = 0
        for path in files:
            content = path.read_text(encoding="utf-8")
            if SOURCE_PATTERN not in content:
                raise DataError(f"{path.name} is missing the required DRAFT marker")
            digest = hashlib.sha256(content.encode()).hexdigest()
            source_ref = f"knowledge/customer/{path.name}"
            ctx.data.execute(
                text("""
                    SELECT customer_rag.stage_draft(
                        :doc_id, :display_name, 1, :source_ref, 'document', :content, :digest, :visibility
                    )
                """),
                {
                    "doc_id": path.stem,
                    "display_name": path.name,
                    "source_ref": source_ref,
                    "content": content,
                    "digest": digest,
                    "visibility": "PUBLIC",
                },
            )
            staged += 1
        counts.rows_out = staged
        counts.detail.update({"published": 0, "draft_chunks_staged": staged})
        ctx.counts.update({"documents_seen": len(files), "draft_chunks_staged": staged, "published": 0})
        ctx.data.commit()
