# ADR-006 RBAC with region and kitchen scope

**Status:** Accepted · **Date:** 2026-11-12

## Context
Roles are Customer, Kitchen Staff, Kitchen Manager, Delivery Agent, Regional Manager and Central Administrator. Regional Managers must be limited to their assigned regions; kitchen roles to their kitchen (#10, #17).

## Decision
Authorization is enforced in the backend on every request: role permission plus a scope (own customer data, kitchen, region, global). The UI only hides controls based on `/me/permissions`; it is never the security boundary. The same checks apply to REST, WebSocket subscriptions, CSV exports, AI tools and pipelines.

## Consequences
- Negative tests (cross-customer, cross-kitchen, cross-region, KS→KM-only, RM→CA-only) are mandatory.
- AI harnesses take scope from the session, never from the prompt.
- Role removal revokes sessions.

## References
Matrix §3.1, §5.1; DDR-31, DDR-64; Task 4.
