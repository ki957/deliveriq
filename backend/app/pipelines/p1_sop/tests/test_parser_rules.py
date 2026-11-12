"""Parser and quality rules on small inputs written from scratch (DDR-102; KITCHEN_SOURCE_VALIDATION §4.2).

Card names here are invented TEST text, never SOP content; they only exercise each reason code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.pipelines.p1_sop.checks import run_checks
from app.pipelines.p1_sop.parser import parse

pytestmark = pytest.mark.unit

FIELDS = """- Preparation: TEST prep
- Portion: 1 TEST portion
- Method: TEST method
- Quality: TEST quality
- Inventory: TEST inventory
- Validation: TEST validation
"""


def card(card_id: str, ingredients: str, *, fields: str = FIELDS) -> str:
    return f"### {card_id} — TEST – Card {card_id}\n- Ingredients per serving:\n{ingredients}{fields}\n"


def doc(*cards: str, declared: int | None = None) -> str:
    count = len(cards) if declared is None else declared
    return f"# TEST\n\n## Menu recipes ({count})\n\n" + "".join(cards) + "## After\n"


def reasons(text: str) -> list[str]:
    return sorted(e.reason_code for e in run_checks(parse(text), is_sop=False).errors)


def test_well_formed_card_parses_with_line_numbers() -> None:
    parsed = parse(doc(card("MENU001", "  - TEST flour: 120 g\n  - TEST milk: 50.5 ml\n")))
    assert parsed.structural_errors == []
    (c,) = parsed.cards
    assert c.card_id == "MENU001" and c.missing_fields() == []
    first, second = c.ingredients
    assert (first.name, first.quantity, first.unit, first.source_line) == ("TEST flour", Decimal(120), "g", 7)
    assert second.original_text == "- TEST milk: 50.5 ml"
    assert reasons(doc(card("MENU001", "  - TEST flour: 120 g\n"))) == []


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("  - TEST flour: 0 g\n", "ZERO_QUANTITY"),
        ("  - TEST flour: 120\n", "MISSING_UNIT"),
        ("  - TEST flour: 120 kg\n", "UNKNOWN_UNIT"),
        ("  - TEST flour: a pinch\n", "BAD_INGREDIENT_LINE"),
    ],
)
def test_bad_ingredient_lines_get_their_reason(line: str, reason: str) -> None:
    assert reasons(doc(card("MENU001", line))) == [reason]


def test_missing_field_is_named() -> None:
    no_quality = FIELDS.replace("- Quality: TEST quality\n", "")
    outcome = run_checks(
        parse(doc(card("MENU001", "  - TEST flour: 1 g\n", fields=no_quality))), is_sop=False
    )
    assert [(e.reason_code, e.message) for e in outcome.errors] == [
        ("MISSING_FIELD", "Missing field: Quality")
    ]


def test_duplicate_card_id_and_multi_unit_name() -> None:
    text = doc(card("MENU001", "  - TEST salt: 1 g\n"), card("MENU001", "  - TEST salt: 1 ml\n"))
    assert reasons(text) == ["DUPLICATE_CARD_ID", "MULTI_UNIT_NAME", "MULTI_UNIT_NAME"]


def test_identical_boms_are_duplicate_candidates_not_errors() -> None:
    same = "  - TEST rice: 100 g\n  - TEST water: 200 ml\n"
    outcome = run_checks(parse(doc(card("MENU001", same), card("MENU002", same))), is_sop=False)
    assert outcome.errors == []
    assert outcome.duplicate_groups == [["MENU001", "MENU002"]]


def test_count_mismatch_fails_the_declared_count_check() -> None:
    outcome = run_checks(parse(doc(card("MENU001", "  - TEST rice: 1 g\n"), declared=2)), is_sop=False)
    check = next(c for c in outcome.checks if c.name == "card_count_matches_declared")
    assert not check.passed and check.failures == 1


def test_structural_faults_are_reported() -> None:
    assert parse("# TEST without a recipe section\n").structural_errors == [
        "No '## Menu recipes (N)' section found"
    ]
    stray = parse("## Menu recipes (1)\nstray text\n" + card("MENU001", "  - TEST rice: 1 g\n"))
    assert stray.structural_errors == ["line 2: content before the first card heading"]
    unknown = parse(doc(card("MENU001", "  - TEST rice: 1 g\n") + "TEST unknown line\n"))
    assert unknown.structural_errors[0].endswith("unrecognised line inside MENU001")


def test_page_footer_is_stripped_and_category_recorded_for_following_cards() -> None:
    footer = " DeliverIQ Kitchen SOP | POC draft — chef validation required Page 3 TEST Category"
    first = card(
        "MENU001",
        "  - TEST rice: 1 g\n",
        fields=FIELDS.replace("TEST validation", "TEST validation" + footer),
    )
    parsed = parse(doc(first, card("MENU002", "  - TEST dal: 1 g\n")))
    one, two = parsed.cards
    assert one.fields["Validation"] == "TEST validation"
    assert one.page_ref == 3
    assert (one.candidate_category, two.candidate_category) == (None, "TEST Category")
    assert [t.kind for t in parsed.transformations] == ["FOOTER_STRIPPED", "CATEGORY_CANDIDATE"]
