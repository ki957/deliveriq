"""Review-queue rules, copied verbatim from docs/KITCHEN_SOURCE_VALIDATION.md §5.1–5.3 (DDR-102).

Each entry names an ingredient exactly as written in the SOP and the reason a human must review it.
Matching is by exact name after whitespace/case normalisation; nothing is inferred. A test asserts
every name here occurs in the SOP, so a typo cannot silently disable a rule. Review items never
change recipe data; resolving them is an owner decision (DDR-33, DDR-34).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewRule:
    reason_code: str
    ingredient: str
    detail: str
    source_ref: str
    #: When set, the rule applies only to these cards (an issue about a combination on one card).
    cards: frozenset[str] | None = None


_SEC_51 = "KITCHEN_SOURCE_VALIDATION.md §5.1"
_SEC_52 = "KITCHEN_SOURCE_VALIDATION.md §5.2"
_SEC_53 = "KITCHEN_SOURCE_VALIDATION.md §5.3"


def _batch(name: str) -> ReviewRule:
    return ReviewRule(
        "MISSING_BATCH_RECIPE", name, "Prepared component without a batch recipe or yield", _SEC_51
    )


def _composite(name: str, detail: str) -> ReviewRule:
    return ReviewRule("COMPOSITE_INGREDIENT", name, detail, _SEC_52)


def _ambiguous(name: str, detail: str, cards: frozenset[str] | None = None) -> ReviewRule:
    return ReviewRule("AMBIGUOUS_INGREDIENT", name, detail, _SEC_53, cards)


_PURCHASED = "Assumed purchased; not stated"
_BUY_OR_MAKE = "Purchased or prepared not stated"

RULES: tuple[ReviewRule, ...] = (
    # §5.1 Prepared components without a batch recipe (8)
    _batch("Idli batter"),
    _batch("Sambhar (prepared)"),
    _batch("Coconut chutney (prepared)"),
    _batch("Onion-tomato gravy (prepared)"),
    _batch("Green chutney (prepared)"),
    _batch("Tamarind chutney (prepared)"),
    _batch("Ginger-garlic paste (prepared)"),
    _batch("Tandoori marinade (prepared)"),
    # §5.2 Composite or unspecified ingredients (buy vs make unknown)
    _composite("Tikka spice mix", "Composition not specified"),
    _composite("Rasam spice mix", "Composition not specified"),
    _composite("Kadhai masala", "Composition not specified"),
    _composite("Pickle spice mix", "Composition not specified"),
    _composite("Cardamom/white pepper mix", "Composite; ratio not specified"),
    _composite("Garam masala", _BUY_OR_MAKE),
    _composite("Vegetable stock", _BUY_OR_MAKE),
    _composite("Salad dressing", "Composition not specified"),
    _composite("Mayonnaise", _BUY_OR_MAKE),
    _composite("Schezwan sauce", _BUY_OR_MAKE),
    _composite("Chilli sauce", _BUY_OR_MAKE),
    _composite("Sweet chilli sauce", _BUY_OR_MAKE),
    _composite("Farsan", _PURCHASED),
    _composite("Boondi", _PURCHASED),
    _composite("Papdi", _PURCHASED),
    _composite("Fried noodles", _PURCHASED),
    _composite("Spring roll sheets", _PURCHASED),
    _composite("Pav", _PURCHASED),
    _composite("Bread", _PURCHASED),
    _composite("Cookies", _PURCHASED),
    _composite("Soya chaap", _PURCHASED),
    # §5.3 Ambiguous ingredient entries
    _ambiguous("Semolina / Rava", "Two names for one item, or alternates? Canonical name needed"),
    _ambiguous("Chickpeas / Chana", "Two names for one item, or alternates? Canonical name needed"),
    _ambiguous("Beans/cabbage mix", "Composite; ratio unknown. Split or treat as one stock item"),
    _ambiguous("Peach/apricot pulp", "Alternate or blend? Clarify"),
    _ambiguous("Tea leaves", "Tea and coffee in one serving, or a choice?", frozenset({"MENU012"})),
    _ambiguous("Coffee powder", "Tea and coffee in one serving, or a choice?", frozenset({"MENU012"})),
    _ambiguous("Squash concentrate", "Flavour unspecified; likely a customization"),
    _ambiguous("Sweet corn", "Possibly the same ingredient as Corn kernels; do not merge without approval"),
    _ambiguous("Corn kernels", "Possibly the same ingredient as Sweet corn; do not merge without approval"),
    _ambiguous("Cheese", "Type unspecified"),
    _ambiguous("Water", "Tracked as inventory? Decide whether non-stock"),
    _ambiguous("Lemon", "Stocked in fractional pieces; confirm the stock unit"),
)


def key(name: str) -> str:
    """Whitespace/case normalisation only (KITCHEN_SOURCE_VALIDATION §4.2 rule 5)."""
    return " ".join(name.split()).lower()


def rules_for(ingredient: str, card_id: str) -> list[ReviewRule]:
    wanted = key(ingredient)
    return [r for r in RULES if key(r.ingredient) == wanted and (r.cards is None or card_id in r.cards)]
