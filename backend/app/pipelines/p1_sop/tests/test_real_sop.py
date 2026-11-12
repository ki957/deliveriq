"""P1 against the committed, hash-checked SOP copy (plan Task 5 import criteria; DATA_PIPELINE §13).

Counts are the SOP's own claims (104 cards, 616 ingredient lines) and the profile recorded in
KITCHEN_SOURCE_VALIDATION.md; the parser must reproduce them without changing any value.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

import pytest

from app.pipelines.p1_sop import report
from app.pipelines.p1_sop.checks import CheckOutcome, run_checks
from app.pipelines.p1_sop.parser import ParseResult, parse
from app.pipelines.p1_sop.pipeline import BLOCKING_SOP_CHECKS, SOP_RELATIVE_PATH
from app.pipelines.p1_sop.review_rules import RULES, key

pytestmark = pytest.mark.unit

SOP = Path(__file__).resolve().parents[5] / "data" / "source" / SOP_RELATIVE_PATH


@lru_cache(maxsize=1)
def _parsed() -> tuple[ParseResult, CheckOutcome]:
    parsed = parse(SOP.read_text(encoding="utf-8"))
    return parsed, run_checks(parsed, is_sop=True)


def test_structure_is_valid_and_counts_match_the_sop_claims() -> None:
    parsed, _ = _parsed()
    assert parsed.structural_errors == []
    assert parsed.declared_count == 104
    assert len(parsed.cards) == 104
    assert sum(len(c.ingredients) for c in parsed.cards) == 616
    assert [c.card_id for c in parsed.cards] == [f"MENU{n:03d}" for n in range(1, 105)]


def test_ingredient_profile() -> None:
    parsed, _ = _parsed()
    lines = [line for card in parsed.cards for line in card.ingredients]
    assert Counter(line.unit for line in lines) == {"g": 483, "ml": 113, "piece": 20}
    assert len({key(line.name) for line in lines}) == 115
    assert all(line.problem is None and line.quantity is not None and line.quantity > 0 for line in lines)


def test_every_card_has_all_8_fields_and_a_line_range() -> None:
    parsed, _ = _parsed()
    for card in parsed.cards:
        assert card.missing_fields() == [], card.card_id
        assert card.source_line_start < card.source_line_end, card.card_id


def test_footers_are_stripped_and_logged_never_kept_in_values() -> None:
    parsed, _ = _parsed()
    kinds = Counter(t.kind for t in parsed.transformations)
    assert kinds["FOOTER_STRIPPED"] == 45
    assert kinds["CONCATENATED_SOP_IGNORED"] == 1
    for card in parsed.cards:
        for value in card.fields.values():
            assert "DeliverIQ Kitchen SOP" not in value, card.card_id


def test_footer_categories_are_candidates_only() -> None:
    parsed, _ = _parsed()
    categories = Counter(c.candidate_category for c in parsed.cards)
    assert categories == {
        None: 12,
        "Welcome Drinks": 13,
        "Soup": 12,
        "Tandoor Starters": 13,
        "Indian Starters": 6,
        "Maharashtrian Starters": 3,
        "Chinese Starters": 13,
        "International Starters": 4,
        "Salads": 12,
        "Raitas": 5,
        "Indian Paneer Menu": 11,
    }
    assert {c.card_id for c in parsed.cards if c.candidate_category is None} == {
        f"MENU{n:03d}" for n in range(1, 13)
    }


def test_quality_checks_pass_and_only_the_known_pair_is_a_duplicate() -> None:
    _, outcome = _parsed()
    assert outcome.errors == []
    assert outcome.rejected_cards() == set()
    assert outcome.duplicate_groups == [["MENU008", "MENU057"]]
    failed = {c.name for c in outcome.checks if not c.passed}
    assert failed == set()
    assert {c.name for c in outcome.checks} >= BLOCKING_SOP_CHECKS


def test_every_review_rule_names_an_ingredient_that_exists_in_the_sop() -> None:
    """A typo in a rule would silently disable it; every rule must match at least one SOP line."""
    parsed, _ = _parsed()
    by_name: dict[str, set[str]] = {}
    for card in parsed.cards:
        for line in card.ingredients:
            by_name.setdefault(key(line.name), set()).add(card.card_id)
    for rule in RULES:
        cards = by_name.get(key(rule.ingredient))
        assert cards, f"{rule.ingredient} does not occur in the SOP"
        if rule.cards is not None:
            assert rule.cards <= cards, rule.ingredient


def test_review_queue_lists_the_8_missing_components_with_reasons() -> None:
    _, outcome = _parsed()
    items = [rule for entries in outcome.review.values() for rule, _ in entries]
    missing = {r.ingredient for r in items if r.reason_code == "MISSING_BATCH_RECIPE"}
    assert len(missing) == 8
    assert {r.reason_code for r in items} == {
        "MISSING_BATCH_RECIPE",
        "COMPOSITE_INGREDIENT",
        "AMBIGUOUS_INGREDIENT",
    }
    assert all(r.detail and r.source_ref.startswith("KITCHEN_SOURCE_VALIDATION.md §5") for r in items)
    # The tea/coffee question is about one card only.
    assert {
        card for card, entries in outcome.review.items() for r, _ in entries if r.ingredient == "Tea leaves"
    } == {"MENU012"}


def test_report_is_deterministic_and_states_the_limitation() -> None:
    parsed, outcome = _parsed()
    totals = report.AppTotals(104, 102, 2, 0, 616, 115, 0, 0)

    def build() -> str:
        return report.build(
            source_path=SOP_RELATIVE_PATH,
            sha256="0" * 64,
            is_fault_input=False,
            parsed=parsed,
            outcome=outcome,
            totals=totals,
        )

    first = build()
    assert first == build()
    assert report.LIMITATION in first
    assert "MENU008" in first and "MENU057" in first


def test_duplicate_reason_uses_the_approved_code_and_names_the_partner() -> None:
    from app.pipelines.p1_sop.pipeline import duplicate_reason

    assert duplicate_reason(["MENU057"]) == (
        "DUPLICATE_BOM: identical ingredient names, quantities and units to MENU057"
    )
