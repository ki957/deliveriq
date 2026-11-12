"""TEST menu fixture definitions (DDR-48, DDR-106, DDR-107; plan §5.2 control 7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cli import fixtures_menu as fx
from app.modules.menu.domain import is_test_name
from app.pipelines.p1_sop.parser import parse
from app.pipelines.p1_sop.pipeline import SOP_RELATIVE_PATH
from app.pipelines.p1_sop.review_rules import key

pytestmark = pytest.mark.unit

SOP = Path(__file__).resolve().parents[4] / "data" / "source" / SOP_RELATIVE_PATH


def test_dishes_match_the_approved_values() -> None:
    assert [(fx.dish_name(letter), price, numbers, live) for letter, price, numbers, live in fx.DISHES] == [
        ("TEST – Synthetic Dish A", 11100, (1, 2), True),
        ("TEST – Synthetic Dish B", 22200, (3, 4), True),
        ("TEST – Synthetic Dish C", 33300, (5, 6), True),
        ("TEST – Synthetic Dish D", 44400, (1, 6), False),
    ]
    assert tuple(f"TEST – Ingredient {n}" for n in range(1, 7)) == fx.INGREDIENTS
    assert fx.LINE_GRAMS == 100


def test_every_fixture_name_carries_the_test_prefix() -> None:
    assert all(is_test_name(name) for name in fx.fixture_names())
    assert fx.TEXT.startswith("TEST – ") and fx.DESCRIPTION.startswith("TEST – ")


def test_no_fixture_name_matches_an_sop_dish_or_ingredient() -> None:
    """Leak control 7: normalized fixture names never equal any of the 104 SOP dish names."""
    parsed = parse(SOP.read_text(encoding="utf-8"))
    sop_names = {key(c.name) for c in parsed.cards} | {
        key(i.name) for c in parsed.cards for i in c.ingredients
    }
    assert len({key(c.name) for c in parsed.cards}) > 90
    stripped = {key(name.removeprefix("TEST – ")) for name in fx.fixture_names()}
    assert not ({key(n) for n in fx.fixture_names()} | stripped) & sop_names
