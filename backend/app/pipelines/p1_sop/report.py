"""Reconciliation report (KITCHEN_SOURCE_VALIDATION §7 step 8). Deterministic: no run ID or timestamps
in the body, so a re-run of the same source produces an identical report (§7 step 9)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.pipelines.p1_sop.checks import CheckOutcome
from app.pipelines.p1_sop.parser import ParseResult

LIMITATION = (
    "The SOP PDF and the Excel mappings are unavailable (KITCHEN_SOURCE_VALIDATION §2). Reconciliation "
    "checks the Markdown for internal consistency only; it cannot detect transcription errors against "
    "the original PDF."
)
FAULT_INPUT_LABEL = "TEST fault file (local/test only; never loaded into app tables)"


@dataclass(frozen=True)
class AppTotals:
    recipes: int
    versions_draft: int
    versions_quarantined: int
    versions_active: int
    ingredient_lines: int
    ingredients: int
    review_items: int
    missing_lineage: int


def build(
    *,
    source_path: str,
    sha256: str,
    is_fault_input: bool,
    parsed: ParseResult,
    outcome: CheckOutcome,
    totals: AppTotals | None,
) -> str:
    lines = [line for card in parsed.cards for line in card.ingredients]
    units = Counter(line.unit or "(none)" for line in lines)
    out: list[str] = [
        "# P1 SOP import — reconciliation report",
        "",
        f"- Source: `{source_path}`",
        f"- SHA-256: `{sha256}`",
        f"- Input: {FAULT_INPUT_LABEL if is_fault_input else 'Kitchen SOP'}",
        "",
        "## Limitation",
        "",
        LIMITATION,
        "",
        "## Source counts",
        "",
        "| Item | Count |",
        "|---|---:|",
        f"| Cards declared in heading | {parsed.declared_count} |",
        f"| Cards parsed | {len(parsed.cards)} |",
        f"| Ingredient lines | {len(lines)} |",
        f"| Distinct ingredient names (exact) | {len({line.name for line in lines})} |",
    ]
    out += [f"| Unit `{unit}` | {count} |" for unit, count in sorted(units.items())]
    out += [
        "",
        "## Checks",
        "",
        "| Check | Severity | Result | Failures | Detail |",
        "|---|---|---|---:|---|",
    ]
    out += [
        f"| {c.name} | {c.severity} | {'pass' if c.passed else 'FAIL'} | {c.failures} | {c.detail} |"
        for c in outcome.checks
    ]

    categories = Counter(card.candidate_category or "(none in source)" for card in parsed.cards)
    out += ["", "## Candidate categories (unconfirmed, DDR-36)", "", "| Category | Cards |", "|---|---:|"]
    out += [f"| {name} | {count} |" for name, count in sorted(categories.items())]

    out += ["", "## Quarantined records", ""]
    if outcome.errors:
        out += ["| Card | Reason | Line | Detail |", "|---|---|---:|---|"]
        out += [
            f"| {e.card_id} | {e.reason_code} | {e.source_line or ''} | {e.message.replace('|', '/')} |"
            for e in sorted(outcome.errors, key=lambda e: (e.source_line or 0, e.reason_code))
        ]
    else:
        out.append("None.")

    out += ["", "## Duplicate candidates (DDR-13: imported, quarantined, never merged)", ""]
    out += [f"- {' / '.join(group)}" for group in outcome.duplicate_groups] or ["None."]

    review = Counter(rule.reason_code for items in outcome.review.values() for rule, _ in items)
    subjects: dict[str, set[str]] = {}
    for items in outcome.review.values():
        for rule, _ in items:
            subjects.setdefault(rule.reason_code, set()).add(rule.ingredient)
    out += [
        "",
        "## Review queue (owner decisions DDR-33, DDR-34)",
        "",
        "| Reason | Items | Ingredients |",
        "|---|---:|---|",
    ]
    out += [
        f"| {reason} | {count} | {', '.join(sorted(subjects[reason]))} |"
        for reason, count in sorted(review.items())
    ]
    out.append(f"\nCards with at least one review item: {len(outcome.review)}")

    kinds = Counter(t.kind for t in parsed.transformations)
    out += ["", "## Transformations (logged; values never changed)", "", "| Kind | Count |", "|---|---:|"]
    out += [f"| {kind} | {count} |" for kind, count in sorted(kinds.items())]

    out += ["", "## Application tables after load", ""]
    if totals is None:
        out.append("Not loaded: fault runs stop at staging (DDR-104)." if is_fault_input else "Not loaded.")
    else:
        out += [
            "| Item | Count |",
            "|---|---:|",
            f"| Recipes from this source | {totals.recipes} |",
            f"| Versions DRAFT | {totals.versions_draft} |",
            f"| Versions QUARANTINED_DUPLICATE_CANDIDATE | {totals.versions_quarantined} |",
            f"| Versions ACTIVE (must be 0, DDR-50) | {totals.versions_active} |",
            f"| Recipe ingredient lines | {totals.ingredient_lines} |",
            f"| SOP-derived ingredients | {totals.ingredients} |",
            f"| Review items | {totals.review_items} |",
            f"| Rows missing lineage (must be 0) | {totals.missing_lineage} |",
        ]
    return "\n".join(out) + "\n"
