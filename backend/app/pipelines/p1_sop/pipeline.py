"""P1 SOP master-data ETL (DATA_PIPELINE §2.3, §5; KITCHEN_SOURCE_VALIDATION §7; DDR-102–DDR-104).

Stages: register → parse → validate structure → transform → quality checks → stage → load DRAFT →
reconcile → report. Nothing reaches `app` tables unless the structure is valid; record-level faults
are quarantined; every loaded row carries lineage; re-runs add zero rows. No SOP recipe is ever
activated (DDR-50): versions load as DRAFT or QUARANTINED_DUPLICATE_CANDIDATE.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from sqlalchemy import Connection, text

from app.core.config import get_pipeline_roles, get_settings
from app.pipelines.framework.context import DataError, RunContext, StructuralError
from app.pipelines.framework.registry import register
from app.pipelines.p1_sop import report
from app.pipelines.p1_sop.checks import CheckOutcome, run_checks
from app.pipelines.p1_sop.parser import ParsedCard, ParseResult, parse
from app.pipelines.p1_sop.review_rules import key
from app.shared.source_registry import parse_inventory

SOP_RELATIVE_PATH = "kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md"
# TEST fault inputs (DDR-104): local/test only, never in images.
FAULT_INPUTS = {
    "fault:records": "p1/test_fault_cards.md",
    "fault:structural": "p1/test_structural_fault.md",
}
KITCHEN_CODE = "KIT-CHN-001"
_NS = uuid.UUID("5c1d2f4e-7d3a-4e8a-9b51-0d6c3a1f9e20")  # fixed namespace: deterministic IDs (DDR-103)
# Reconciliation checks that must pass before the real SOP loads anything.
BLOCKING_SOP_CHECKS = frozenset(
    {
        "card_count_matches_declared",
        "matches_sop_stated_card_count",
        "matches_sop_stated_line_count",
        "card_id_sequence_has_no_gaps",
    }
)


def duplicate_reason(partners: list[str]) -> str:
    """Kept, never merged (DDR-13); names what was compared: the ingredient list only."""
    return f"DUPLICATE_BOM: identical ingredient names, quantities and units to {', '.join(partners)}"


def stable_id(*parts: str) -> uuid.UUID:
    return uuid.uuid5(_NS, "|".join(parts))


# ---------------------------------------------------------------- stage 1: register
def _register(ctx: RunContext) -> tuple[str, bytes, str, bool]:
    roles = get_pipeline_roles()
    with ctx.stage("register") as counts:
        if ctx.input_ref in (None, "sop"):
            path, is_fault = Path(roles.source_root) / SOP_RELATIVE_PATH, False
        elif ctx.input_ref in FAULT_INPUTS:
            if not (get_settings().is_local_or_test and ctx.is_test):
                raise DataError("Fault-injection runs are allowed only as test runs in local/test (DDR-65)")
            path, is_fault = Path(roles.test_inputs_root) / FAULT_INPUTS[ctx.input_ref], True
        else:
            raise DataError(f"Unknown P1 input: {ctx.input_ref}")
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            raise StructuralError(f"Input file not found: {path.name}") from None
        sha = hashlib.sha256(content).hexdigest()

        expected = None
        if not is_fault:
            inventory = parse_inventory(Path(roles.inventory_path).read_text(encoding="utf-8"))
            expected = next((s.sha256 for s in inventory if s.path == SOP_RELATIVE_PATH), None)
        status = "OK" if is_fault or sha == expected else "HASH_MISMATCH"
        ctx.records.execute(
            text(
                "INSERT INTO ops.source_registry (run_id, source_path, expected_sha256, "
                "observed_sha256, size_bytes, "
                "line_count, status) VALUES (:r, :p, :e, :o, :s, :l, :st)"
            ),
            {
                "r": ctx.run_id,
                "p": str(path),
                "e": expected,
                "o": sha,
                "s": len(content),
                "l": content.count(b"\n"),
                "st": status,
            },
        )
        counts.detail.update({"sha256": sha, "expected": expected, "fault_input": is_fault})
        if status != "OK":
            raise StructuralError(
                "SOP hash differs from the inventory: an approved inventory update is required"
            )
        return str(path), content, sha, is_fault


# ---------------------------------------------------------------- stages 2–5
def _parse_and_check(ctx: RunContext, content: bytes, is_fault: bool) -> tuple[ParseResult, CheckOutcome]:
    with ctx.stage("parse") as counts:
        try:
            parsed = parse(content.decode("utf-8"))
        except UnicodeDecodeError:
            raise StructuralError("Input is not valid UTF-8") from None
        counts.rows_out = len(parsed.cards)
        counts.detail["ingredient_lines"] = sum(len(c.ingredients) for c in parsed.cards)

    with ctx.stage("validate structure") as counts:
        counts.rows_in = len(parsed.cards)
        if parsed.structural_errors:
            counts.detail["errors"] = parsed.structural_errors[:20]
            for message in parsed.structural_errors:
                ctx.error("validate structure", None, "STRUCTURE", message)
            raise StructuralError(f"Structure invalid: {parsed.structural_errors[0]} — nothing loaded")

    with ctx.stage("transform") as counts:
        counts.rows_out = len(parsed.transformations)
        counts.detail["transformations"] = [
            {"line": t.source_line, "kind": t.kind, "detail": t.detail} for t in parsed.transformations
        ]

    with ctx.stage("quality checks") as counts:
        outcome = run_checks(parsed, is_sop=not is_fault)
        for error in outcome.errors:
            ref = f"{error.card_id}@{error.source_line}" if error.source_line else error.card_id
            ctx.error("quality checks", ref, error.reason_code, error.message)
        for check in outcome.checks:
            ctx.dq(check.name, check.severity, check.passed, check.failures, {"detail": check.detail})
        counts.rows_in = len(parsed.cards)
        counts.rows_rejected = len(outcome.rejected_cards())
        counts.detail["review_cards"] = len(outcome.review)
        blocking = [c.name for c in outcome.checks if not c.passed and c.name in BLOCKING_SOP_CHECKS]
        if blocking and not is_fault:
            raise DataError(f"Reconciliation failed ({', '.join(blocking)}); nothing loaded")
    return parsed, outcome


# ---------------------------------------------------------------- stage 6: staging
def _stage(ctx: RunContext, parsed: ParseResult, outcome: CheckOutcome) -> None:
    rejected, duplicates = outcome.rejected_cards(), outcome.duplicate_cards()
    with ctx.stage("stage") as counts, ctx.data.begin():
        # A retried run (transient failure after this stage committed) restages from scratch.
        for table in ("staging.sop_ingredient_lines", "staging.sop_cards"):
            ctx.data.execute(text(f"DELETE FROM {table} WHERE run_id = :r"), {"r": ctx.run_id})  # noqa: S608
        for card in parsed.cards:
            status = (
                "REJECTED"
                if card.card_id in rejected
                else "DUPLICATE_CANDIDATE"
                if card.card_id in duplicates
                else "VALID"
            )
            ctx.data.execute(
                text(
                    "INSERT INTO staging.sop_cards (run_id, source_line_start, source_line_end, "
                    "card_id, name, status, "
                    "fields, page_ref, candidate_category) VALUES (:r, :s, :e, :c, :n, :st, CAST(:f "
                    "AS jsonb), :p, :cat)"
                ),
                {
                    "r": ctx.run_id,
                    "s": card.source_line_start,
                    "e": card.source_line_end,
                    "c": card.card_id,
                    "n": card.name,
                    "st": status,
                    "f": json.dumps(card.fields),
                    "p": card.page_ref,
                    "cat": card.candidate_category,
                },
            )
            for line in card.ingredients:
                ctx.data.execute(
                    text(
                        "INSERT INTO staging.sop_ingredient_lines (run_id, source_line, card_line, "
                        "line_no, original_text, "
                        "name, quantity, unit, problem) VALUES (:r, :sl, :cl, :n, :t, :nm, :q, :u, :p)"
                    ),
                    {
                        "r": ctx.run_id,
                        "sl": line.source_line,
                        "cl": card.source_line_start,
                        "n": line.line_no,
                        "t": line.original_text,
                        "nm": line.name,
                        "q": line.quantity,
                        "u": line.unit,
                        "p": line.problem,
                    },
                )
        counts.rows_out = len(parsed.cards)
        counts.rows_rejected = len(rejected)


# ---------------------------------------------------------------- stage 7: load DRAFT
def _set_actor(conn: Connection, run_id: uuid.UUID) -> None:
    conn.execute(text("SELECT set_config('app.actor_role', 'SYSTEM', true)"))
    conn.execute(text("SELECT set_config('app.reason', 'P1 SOP import', true)"))
    conn.execute(text("SELECT set_config('app.correlation_id', :c, true)"), {"c": str(run_id)})


def _load(ctx: RunContext, path: str, sha: str, parsed: ParseResult, outcome: CheckOutcome) -> dict[str, int]:
    rejected = outcome.rejected_cards()
    partners = {card: [o for o in group if o != card] for group in outcome.duplicate_groups for card in group}
    added = {"ingredients": 0, "recipes": 0, "recipe_versions": 0, "recipe_ingredients": 0, "review_items": 0}
    loadable = [c for c in parsed.cards if c.card_id not in rejected]
    with ctx.stage("load DRAFT") as counts, ctx.data.begin():
        _set_actor(ctx.data, ctx.run_id)
        kitchen_id = ctx.data.execute(
            text("SELECT id FROM app.kitchens WHERE code = :c"), {"c": KITCHEN_CODE}
        ).scalar_one()

        names = {key(line.name): line for card in loadable for line in card.ingredients}
        for norm, line in sorted(names.items()):
            added["ingredients"] += ctx.data.execute(
                text(
                    "INSERT INTO app.ingredients (id, name, unit, origin, source_sha256) "
                    "SELECT :id, :n, :u, 'SOP_DERIVED', :sha WHERE NOT EXISTS "
                    "(SELECT 1 FROM app.ingredients WHERE lower(name) = :k)"
                ),
                {"id": stable_id("ingredient", norm), "n": line.name, "u": line.unit, "sha": sha, "k": norm},
            ).rowcount
        ingredient_ids = {
            row.k: row.id
            for row in ctx.data.execute(
                text("SELECT lower(name) AS k, id FROM app.ingredients WHERE lower(name) = ANY(:ks)"),
                {"ks": list(names)},
            )
        }

        for card in loadable:
            added.update(
                _load_card(
                    ctx.data,
                    ctx.run_id,
                    card,
                    kitchen_id,
                    path,
                    sha,
                    ingredient_ids,
                    outcome,
                    duplicate_of=partners.get(card.card_id, []),
                    added=added,
                )
            )
        counts.rows_in = len(loadable)
        counts.rows_out = added["recipe_versions"]
        counts.detail["added"] = dict(added)
    return added


def _load_card(
    conn: Connection,
    run_id: uuid.UUID,
    card: ParsedCard,
    kitchen_id: uuid.UUID,
    path: str,
    sha: str,
    ingredient_ids: dict[str, uuid.UUID],
    outcome: CheckOutcome,
    *,
    duplicate_of: list[str],
    added: dict[str, int],
) -> dict[str, int]:
    recipe_id = stable_id("recipe", card.card_id)
    version_id = stable_id("recipe_version", card.card_id, "1")
    added["recipes"] += conn.execute(
        text(
            "INSERT INTO app.recipes (id, kitchen_id, source_menu_id, name) SELECT :id, :k, :m, :n "
            "WHERE NOT EXISTS (SELECT 1 FROM app.recipes WHERE id = :id OR source_menu_id = :m)"
        ),
        {"id": recipe_id, "k": kitchen_id, "m": card.card_id, "n": card.name},
    ).rowcount
    f = card.fields
    added["recipe_versions"] += conn.execute(
        text(
            "INSERT INTO app.recipe_versions (id, recipe_id, version, status, quarantine_reason, "
            "prep_type, portion, "
            "method, quality, inventory_rule, validation_text, source_sha256, source_line_start, "
            "source_line_end, "
            "source_path, source_card_id, source_page_ref, candidate_category, import_run_id, imported_at) "
            "SELECT :id, :rid, 1, :st, :qr, :prep, :portion, :method, :quality, :inv, :val, :sha, "
            ":ls, :le, :path, "
            ":card, :page, :cat, :run, now() WHERE NOT EXISTS (SELECT 1 FROM app.recipe_versions "
            "WHERE id = :id)"
        ),
        {
            "id": version_id,
            "rid": recipe_id,
            "st": "QUARANTINED_DUPLICATE_CANDIDATE" if duplicate_of else "DRAFT",
            "qr": duplicate_reason(duplicate_of) if duplicate_of else None,
            "prep": f.get("Preparation"),
            "portion": f.get("Portion"),
            "method": f.get("Method"),
            "quality": f.get("Quality"),
            "inv": f.get("Inventory"),
            "val": f.get("Validation"),
            "sha": sha,
            "ls": card.source_line_start,
            "le": card.source_line_end,
            "path": path,
            "card": card.card_id,
            "page": card.page_ref,
            "cat": card.candidate_category,
            "run": run_id,
        },
    ).rowcount
    for line in card.ingredients:
        added["recipe_ingredients"] += conn.execute(
            text(
                "INSERT INTO app.recipe_ingredients (id, recipe_version_id, line_no, ingredient_id, "
                "quantity, unit, "
                "source_line, original_text, source_sha256) SELECT :id, :v, :n, :i, :q, :u, :sl, :t, :sha "
                "WHERE NOT EXISTS (SELECT 1 FROM app.recipe_ingredients WHERE recipe_version_id = :v "
                "AND line_no = :n)"
            ),
            {
                "id": stable_id("recipe_ingredient", card.card_id, "1", str(line.line_no)),
                "v": version_id,
                "n": line.line_no,
                "i": ingredient_ids[key(line.name)],
                "q": line.quantity,
                "u": line.unit,
                "sl": line.source_line,
                "t": line.original_text,
                "sha": sha,
            },
        ).rowcount
    for rule, source_line in outcome.review.get(card.card_id, []):
        added["review_items"] += conn.execute(
            text(
                "INSERT INTO app.recipe_review_items (recipe_version_id, reason_code, subject, "
                "detail, source_ref, "
                "source_line, import_run_id) SELECT :v, :c, :s, :d, :ref, :l, :run WHERE NOT EXISTS "
                "(SELECT 1 FROM app.recipe_review_items WHERE recipe_version_id = :v AND reason_code "
                "= :c AND subject = :s)"
            ),
            {
                "v": version_id,
                "c": rule.reason_code,
                "s": rule.ingredient,
                "d": rule.detail,
                "ref": rule.source_ref,
                "l": source_line,
                "run": run_id,
            },
        ).rowcount
    return added


# ---------------------------------------------------------------- stage 8: reconcile
def _reconcile(ctx: RunContext, sha: str) -> report.AppTotals:
    with ctx.stage("reconcile") as counts:
        row = ctx.records.execute(
            text(
                """
                SELECT
                  (SELECT count(DISTINCT v.recipe_id) FROM app.recipe_versions v WHERE v.source_sha256 =
                      :sha),
                  (SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = :sha AND status = 'DRAFT'),
                  (SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = :sha
                      AND status = 'QUARANTINED_DUPLICATE_CANDIDATE'),
                  (SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = :sha AND status = 'ACTIVE'),
                  (SELECT count(*) FROM app.recipe_ingredients WHERE source_sha256 = :sha),
                  (SELECT count(*) FROM app.ingredients WHERE origin = 'SOP_DERIVED' AND source_sha256 =
                      :sha),
                  (SELECT count(*) FROM app.recipe_review_items r JOIN app.recipe_versions v ON v.id =
                      r.recipe_version_id
                      WHERE v.source_sha256 = :sha),
                  (SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = :sha AND
                      (source_card_id IS NULL
                      OR source_line_start IS NULL OR source_path IS NULL OR import_run_id IS NULL))
                  + (SELECT count(*) FROM app.recipe_ingredients WHERE source_sha256 = :sha
                      AND (source_line IS NULL OR original_text IS NULL))
                """
            ),
            {"sha": sha},
        ).one()
        totals = report.AppTotals(*row)
        ctx.dq(
            "no_sop_recipe_active",
            "critical",
            totals.versions_active == 0,
            totals.versions_active,
            {"rule": "DDR-50"},
        )
        ctx.dq(
            "lineage_complete",
            "critical",
            totals.missing_lineage == 0,
            totals.missing_lineage,
            {"rule": "KITCHEN_SOURCE_VALIDATION §9"},
        )
        counts.detail["totals"] = totals.__dict__
        if totals.versions_active or totals.missing_lineage:
            raise DataError("Post-load reconciliation failed (active SOP recipe or missing lineage)")
        return totals


# ---------------------------------------------------------------- entry point
@register("p1_sop")
def run(ctx: RunContext) -> None:
    path, content, sha, is_fault = _register(ctx)
    parsed, outcome = _parse_and_check(ctx, content, is_fault)
    _stage(ctx, parsed, outcome)

    totals = None
    if is_fault:
        with ctx.stage("load DRAFT") as counts:
            counts.detail["skipped"] = "Fault runs stop at staging and never load into app tables (DDR-104)"
    else:
        ctx.counts["added"] = _load(ctx, path, sha, parsed, outcome)
        totals = _reconcile(ctx, sha)

    with ctx.stage("report") as counts:
        markdown = report.build(
            source_path=Path(path).name if is_fault else SOP_RELATIVE_PATH,
            sha256=sha,
            is_fault_input=is_fault,
            parsed=parsed,
            outcome=outcome,
            totals=totals,
        )
        ctx.save_report(markdown)
        counts.rows_out = len(markdown)
    ctx.counts.update(
        {
            "cards": len(parsed.cards),
            "ingredient_lines": sum(len(c.ingredients) for c in parsed.cards),
            "quarantined_records": len(outcome.errors),
            "duplicate_candidates": len(outcome.duplicate_cards()),
            "review_cards": len(outcome.review),
        }
    )
