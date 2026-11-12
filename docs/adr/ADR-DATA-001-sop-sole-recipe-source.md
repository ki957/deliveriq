# ADR-DATA-001 SOP Markdown as the sole recipe source

**Status:** Accepted · **Date:** 2026-11-12

## Context
The ETL spec and Business brief cite Excel workbooks (ingredient mapping, consolidated kitchen data, tandoor standards) and an SOP PDF. None is available; the mapping workbook was deleted by the owner.

## Decision
`data/source/kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` (SHA-256 `7ee63f62…bfc19211`) is the only real recipe source: 104 cards, 616 ingredient lines, units g / ml / piece. All recipes import as DRAFT, MENU008/MENU057 are quarantined, and no SOP recipe is activated in this POC. Demo dishes are independently created `TEST –` items.

## Consequences
- No values are inferred from missing workbooks.
- Missing dish data (prices, tax, descriptions, allergens) is out of POC scope (DDR-32).

## References
DDR-09, DDR-13, DDR-48, DDR-50; `KITCHEN_SOURCE_VALIDATION.md`; inventory §1.2.
