"""P1 quality checks (DATA_PIPELINE §7, KITCHEN_SOURCE_VALIDATION §4.2 and §8). Pure, no I/O."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.pipelines.p1_sop.parser import UNITS, ParsedCard, ParseResult
from app.pipelines.p1_sop.review_rules import ReviewRule, key, rules_for

# Counts the SOP states about itself ("Source extraction notes"); checked, never assumed.
SOP_STATED_CARDS = 104
SOP_STATED_LINES = 616


@dataclass(frozen=True)
class RecordError:
    card_id: str
    reason_code: str
    message: str
    source_line: int | None


@dataclass(frozen=True)
class QualityCheck:
    name: str
    severity: str  # critical | warning
    passed: bool
    failures: int
    detail: str


@dataclass
class CheckOutcome:
    errors: list[RecordError] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    review: dict[str, list[tuple[ReviewRule, int]]] = field(default_factory=dict)  # card -> (rule, line)
    checks: list[QualityCheck] = field(default_factory=list)

    def rejected_cards(self) -> set[str]:
        """Cards with record-level faults: quarantined in staging, never loaded (DDR-67 rule 3)."""
        return {e.card_id for e in self.errors}

    def duplicate_cards(self) -> set[str]:
        return {card for group in self.duplicate_groups for card in group}


def _bom(card: ParsedCard) -> tuple[tuple[str, str, str | None], ...]:
    return tuple(sorted((key(i.name), str(i.quantity), i.unit) for i in card.ingredients))


def run_checks(parsed: ParseResult, *, is_sop: bool) -> CheckOutcome:
    out = CheckOutcome()
    cards = parsed.cards
    lines = [line for card in cards for line in card.ingredients]

    # ---------------------------------------------------------------- record-level faults
    for card in cards:
        for missing in card.missing_fields():
            out.errors.append(
                RecordError(
                    card.card_id, "MISSING_FIELD", f"Missing field: {missing}", card.source_line_start
                )
            )
        for line in card.ingredients:
            if line.problem:
                out.errors.append(
                    RecordError(card.card_id, line.problem, line.original_text, line.source_line)
                )

    seen: dict[str, int] = {}
    for card in cards:
        if card.card_id in seen:
            out.errors.append(
                RecordError(
                    card.card_id,
                    "DUPLICATE_CARD_ID",
                    f"Card ID also used at line {seen[card.card_id]}",
                    card.source_line_start,
                )
            )
        seen.setdefault(card.card_id, card.source_line_start)

    units_by_name: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        if line.unit:
            units_by_name[key(line.name)].add(line.unit)
    multi_unit = {name for name, units in units_by_name.items() if len(units) > 1}
    for card in cards:
        for line in card.ingredients:
            if key(line.name) in multi_unit:
                out.errors.append(
                    RecordError(
                        card.card_id,
                        "MULTI_UNIT_NAME",
                        f"{line.name} is used with units {sorted(units_by_name[key(line.name)])}",
                        line.source_line,
                    )
                )

    # ---------------------------------------------------------------- duplicates (DDR-13): quarantine, keep
    by_bom: dict[tuple[tuple[str, str, str | None], ...], list[str]] = defaultdict(list)
    for card in cards:
        if card.ingredients and card.card_id not in out.rejected_cards():
            by_bom[_bom(card)].append(card.card_id)
    out.duplicate_groups = [ids for ids in by_bom.values() if len(ids) > 1]

    # ---------------------------------------------------------------- review queue (DDR-102)
    for card in cards:
        items = [
            (rule, line.source_line)
            for line in card.ingredients
            for rule in rules_for(line.name, card.card_id)
        ]
        if items:
            out.review[card.card_id] = items

    # ---------------------------------------------------------------- reconciliation checks
    ids = [c.card_id for c in cards]
    numbers = sorted(int(i[4:]) for i in ids if re.fullmatch(r"MENU\d{3}", i))
    gaps = sorted(set(range(1, (numbers[-1] if numbers else 0) + 1)) - set(numbers))

    def add(name: str, passed: bool, failures: int, detail: str, severity: str = "critical") -> None:
        out.checks.append(QualityCheck(name, severity, passed, failures, detail))

    add(
        "card_count_matches_declared",
        parsed.declared_count == len(cards),
        abs((parsed.declared_count or 0) - len(cards)),
        f"declared {parsed.declared_count}, parsed {len(cards)}",
    )
    add(
        "unique_card_ids",
        len(set(ids)) == len(ids),
        len(ids) - len(set(ids)),
        f"{len(set(ids))} unique of {len(ids)}",
    )
    add(
        "cards_with_all_8_fields",
        all(not c.missing_fields() for c in cards),
        sum(1 for c in cards if c.missing_fields()),
        "heading + 7 fields per card",
    )
    add(
        "ingredient_lines_well_formed",
        all(not line.problem for line in lines),
        sum(1 for line in lines if line.problem),
        f"{len(lines)} lines",
    )
    add(
        "units_in_allowed_set",
        all(line.unit in UNITS for line in lines if line.unit),
        sum(1 for line in lines if line.unit and line.unit not in UNITS),
        "g, ml, piece",
    )
    add(
        "quantities_positive",
        all(line.quantity is None or line.quantity > 0 for line in lines),
        sum(1 for line in lines if line.quantity is not None and line.quantity <= 0),
        "quantity > 0",
    )
    add("no_name_with_two_units", not multi_unit, len(multi_unit), ", ".join(sorted(multi_unit)) or "none")
    add(
        "duplicate_bom_groups",
        True,
        len(out.duplicate_groups),
        "; ".join("/".join(g) for g in out.duplicate_groups) or "none",
        severity="warning",
    )
    if is_sop:
        add(
            "matches_sop_stated_card_count",
            len(cards) == SOP_STATED_CARDS,
            abs(len(cards) - SOP_STATED_CARDS),
            f"SOP states {SOP_STATED_CARDS}; parsed {len(cards)}",
        )
        add(
            "matches_sop_stated_line_count",
            len(lines) == SOP_STATED_LINES,
            abs(len(lines) - SOP_STATED_LINES),
            f"SOP states {SOP_STATED_LINES}; parsed {len(lines)}",
        )
        add(
            "card_id_sequence_has_no_gaps",
            not gaps,
            len(gaps),
            ", ".join(f"MENU{n:03d}" for n in gaps) or "none",
        )
    return out
