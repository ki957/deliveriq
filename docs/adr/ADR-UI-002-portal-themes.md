# ADR-UI-002 Per-portal theme tokens and palettes

**Status:** Accepted · **Date:** 2026-11-12

## Context
Older consolidated specs assign Palette A to Customer; the portal-specific documents assign Palette B to Customer and Palette A to Delivery. `shareddsah/` has no design-system document.

## Decision
- Customer: `#A8C9CB`, `#FFFFFF`, `#F45B0B` (Palette B).
- Delivery: `#FFF21A`, `#171717`, `#A66BFF` (Palette A).
- Kitchen: `#D5360C`, `#E6D58D`, `#101010`.
- Management: `#021861`, `#255DCE`, `#DE1110`, `#FFFFFF`, `#F3F5FA`; red sparingly.
Shared token structure (DDR-21): colour roles, identical semantic status colours, 4 px spacing, restrained radius, Tailwind breakpoints + KDS check at ≥ 1920 px, 2 px focus ring, 44 px touch targets. Inter, self-hosted (DDR-22). Concrete status colours are chosen at Task 4, contrast-checked and shown to the owner.

## Consequences
- Palettes A and B are never blended.
- The older palette sections are historical and not edited.

## References
DDR-01, 02, 04, 05, 21, 22.
