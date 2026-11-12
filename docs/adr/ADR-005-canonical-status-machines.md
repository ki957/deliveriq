# ADR-005 Canonical status machines

**Status:** Accepted · **Date:** 2026-11-12

## Context
Each portal document uses its own order-status vocabulary (#1 §10, #4 §6.1, #7 §5, #19 §13, Harness blueprint §8.1).

## Decision
The backend stores independent state machines: fulfilment (`orders.fulfilment_status`), payment, delivery assignment and item preparation. Portals derive display labels from one mapping (`PORTAL_REQUIREMENTS_MATRIX.md` §7.3). Assignment never changes fulfilment status. `PICKED_UP → OUT_FOR_DELIVERY` happens automatically after a validated pickup, in the same transaction.

## Consequences
- Illegal transitions are rejected in the domain layer and by DB constraints.
- "Agent Assigned" is an indicator added to the fulfilment label, not a status.
- No portal may invent a status.

## References
DDR-16, DDR-17; Matrix §7.
