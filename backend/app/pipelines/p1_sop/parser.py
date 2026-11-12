"""Deterministic line parser for the Kitchen SOP Markdown (KITCHEN_SOURCE_VALIDATION §7 step 2).

Standard library only, no I/O beyond the text passed in. Values are never changed: the only
transformations are logged footer stripping and whitespace normalisation (DATA_PIPELINE §8, DDR-102).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

UNITS = frozenset({"g", "ml", "piece"})
FIELDS = ("Preparation", "Portion", "Ingredients", "Method", "Quality", "Inventory", "Validation")

_SECTION = re.compile(r"^## Menu recipes \((\d+)\)\s*$")
_NEXT_SECTION = re.compile(r"^## ")
_CARD = re.compile(r"^### (MENU\d{3}|TEST – [^—]+?) — (.+?)\s*$")
_FIELD = re.compile(r"^- (Preparation|Portion|Method|Quality|Inventory|Validation):\s*(.*)$")
_INGREDIENTS = re.compile(r"^- Ingredients per serving:\s*$")
_INGREDIENT = re.compile(r"^  - (.+?):\s*(.*)$")
_QTY_UNIT = re.compile(r"^(\d+(?:\.\d+)?)\s+(\S+)$")
_QTY_ONLY = re.compile(r"^(\d+(?:\.\d+)?)$")
# Page footer appended to field text:
#   "DeliverIQ Kitchen SOP | POC draft — chef validation required Page N [text]"
_FOOTER = re.compile(
    r"\s*DeliverIQ Kitchen SOP \| POC draft — chef validation required Page (\d+)(?:\s+(.*))?$"
)
# The last footer carries a concatenated copy of the inventory-command SOP and checklist (§5.6).
_CONCATENATED_SOP = "Kitchen AI command"


@dataclass(frozen=True)
class IngredientLine:
    line_no: int  # position within the card, 1-based
    source_line: int  # line in the file, 1-based
    original_text: str
    name: str
    quantity: Decimal | None
    unit: str | None
    problem: str | None  # reason code when the line cannot be used as written


@dataclass
class ParsedCard:
    card_id: str
    name: str
    source_line_start: int
    source_line_end: int = 0
    fields: dict[str, str] = field(default_factory=dict)
    ingredients: list[IngredientLine] = field(default_factory=list)
    has_ingredients_block: bool = False
    page_ref: int | None = None
    candidate_category: str | None = None

    def missing_fields(self) -> list[str]:
        missing = [f for f in FIELDS if f != "Ingredients" and not self.fields.get(f)]
        if not self.has_ingredients_block or not self.ingredients:
            missing.insert(2, "Ingredients")
        return missing


@dataclass(frozen=True)
class Transformation:
    source_line: int
    kind: str
    detail: str


@dataclass
class ParseResult:
    declared_count: int | None
    cards: list[ParsedCard]
    transformations: list[Transformation]
    structural_errors: list[str]


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _parse_value(text: str) -> tuple[Decimal | None, str | None, str | None]:
    value = text.strip()
    try:
        if match := _QTY_UNIT.match(value):
            quantity, unit = Decimal(match[1]), match[2]
            if quantity <= 0:
                return quantity, unit, "ZERO_QUANTITY"
            return quantity, unit, None if unit in UNITS else "UNKNOWN_UNIT"
        if match := _QTY_ONLY.match(value):
            return Decimal(match[1]), None, "MISSING_UNIT"
    except InvalidOperation:  # pragma: no cover - the regexes only admit valid decimals
        pass
    return None, None, "BAD_INGREDIENT_LINE"


def parse(text: str) -> ParseResult:
    lines = text.splitlines()
    result = ParseResult(declared_count=None, cards=[], transformations=[], structural_errors=[])

    start = next((i for i, line in enumerate(lines) if _SECTION.match(line)), None)
    if start is None:
        result.structural_errors.append("No '## Menu recipes (N)' section found")
        return result
    declared = _SECTION.match(lines[start])
    result.declared_count = int(declared[1]) if declared else None

    card: ParsedCard | None = None
    in_ingredients = False
    category: str | None = None  # a footer category labels the cards that follow it

    def close(end_line: int) -> None:
        if card is not None:
            card.source_line_end = end_line

    last_content = start + 1
    for index in range(start + 1, len(lines)):
        number = index + 1
        raw = lines[index]
        if _NEXT_SECTION.match(raw):
            break
        if not raw.strip():
            continue
        last_content = number

        if heading := _CARD.match(raw):
            close(number - 1)
            card = ParsedCard(
                card_id=heading[1],
                name=_normalise(heading[2]),
                source_line_start=number,
                candidate_category=category,
            )
            result.cards.append(card)
            in_ingredients = False
            continue

        if card is None:
            result.structural_errors.append(f"line {number}: content before the first card heading")
            continue

        if _INGREDIENTS.match(raw):
            card.has_ingredients_block = True
            in_ingredients = True
            continue

        if in_ingredients and (item := _INGREDIENT.match(raw)):
            quantity, unit, problem = _parse_value(item[2])
            card.ingredients.append(
                IngredientLine(
                    line_no=len(card.ingredients) + 1,
                    source_line=number,
                    original_text=raw.strip(),
                    name=_normalise(item[1]),
                    quantity=quantity,
                    unit=unit,
                    problem=problem,
                )
            )
            continue

        if field_match := _FIELD.match(raw):
            in_ingredients = False
            label, value = field_match[1], field_match[2]
            if footer := _FOOTER.search(value):
                value = value[: footer.start()]
                card.page_ref = int(footer[1])
                trailing = (footer[2] or "").strip()
                result.transformations.append(
                    Transformation(number, "FOOTER_STRIPPED", f"page {footer[1]} footer removed from {label}")
                )
                if trailing.startswith(_CONCATENATED_SOP):
                    result.transformations.append(
                        Transformation(
                            number,
                            "CONCATENATED_SOP_IGNORED",
                            "concatenated copy of the inventory-command SOP and release checklist "
                            "ignored; the formatted sections are the source of record",
                        )
                    )
                elif trailing:
                    category = _normalise(trailing)
                    result.transformations.append(
                        Transformation(
                            number,
                            "CATEGORY_CANDIDATE",
                            f"'{category}' recorded as candidate category for the following cards",
                        )
                    )
            card.fields[label] = _normalise(value)
            continue

        result.structural_errors.append(f"line {number}: unrecognised line inside {card.card_id}")

    close(last_content)
    if not result.cards and not result.structural_errors:
        result.structural_errors.append("No recipe cards found")
    return result
