# Management module (unified RM / CA read views, staff access, exports)

**Purpose and scope:** the backend of the unified management portal (#10; MG-01, MG-03, MG-08; DDR-114). Read models are scoped to the caller: a Regional Manager sees assigned regions only, a Central Administrator sees everything; anything outside scope reads as 404. Operational actions (kitchen settings, unavailability approval, agent assignment, force-offline, failure decisions, code reissue) reuse the owning modules' existing routes; this module never duplicates them. The screens are Task 10B; WebSocket scope is tested in Task 11A (`realtime` module); Reports are Task 13; AI is Task 15.

| Item | Value |
| --- | --- |
| UI screens | Management portal (Task 10B; `frontend/src/features/management/README.md`) |
| API endpoints | `/api/v1/management`: `GET /overview` · `GET /regions` · `GET /kitchens` · `GET /orders` (filters, 50 per page) · `GET /orders.csv` · `GET /orders/{id}` (items and timeline) · `GET /deliveries` · `GET /refunds` (read-only) · `GET /kitchens/{id}/inventory` · `GET /audit` (50 per page) · `GET /audit.csv` · `GET /staff` · `POST /staff` · `POST /staff/roles/{assignment_id}/remove` · `PUT /staff/{user_id}/status` |
| Service functions | `overview`, `kitchen_list`, `region_list`, `order_list`, `order_detail`, `orders_csv`, `delivery_board`, `refund_list`, `inventory`, `audit_list`, `audit_csv`, `staff_list`, `add_staff`, `remove_role`, `set_active` |
| Tables | Reads orders, status history, assignments, payments/refunds, stock and ledger, `app.audit_events`. Writes only `app.users`, `app.role_assignments`, `app.sessions` (and device revocation) plus audit events. No migration: sessions already require `u.status = 'ACTIVE'` and grants are read per request, so a removed role or a deactivation takes effect on the next request |
| Permissions | `management.operations.view` (overview, orders, deliveries, refunds); `management.inventory.view` (new, code-only, DDR-114 (12)); `management.audit.regional` / `management.audit.global`; `management.staff.manage` (KM, KS, DA in the RM's regions); `management.regional_managers.manage` (CA only) |
| States | 200 · 201 · 204 · 401 · 403 (no grant, self-escalation) · 404 (outside scope) · 409 (duplicate role, deactivated account, active delivery) · 422 (reason, range > 31 days, export > 5,000 rows, bad mobile, kitchen/region mismatch) |
| Tests | `tests/test_management_integration.py` (7 tests: scope across every view and CSV; bounded date ranges; order timeline and refund record with exceptional refunds disabled; staff provisioning scope and no self-escalation; immediate role removal and deactivation with the active-delivery block; audit scope and audited export; overview counts); `app/core/tests/test_permissions.py` (inventory permission) |

## Rules implemented

- **Scope (plan Task 10 criterion 1):** `scope()` returns every region only for a global grant; otherwise the regions the permission is granted in; no grant is 403. Out-of-scope rows are filtered in SQL, and single-row reads return 404.
- **Staff access (DDR-114 (3)–(5), MG-01):** an RM grants and removes KM, KS and DA in their own regions; a CA also manages RMs. No CA is created or removed here. Kitchen roles need a kitchen in the region; other roles must not have one. A person cannot change their own access. Every change needs a reason and is audited.
- **Removal and deactivation:** revokes sessions and devices at once. For an agent, only an ACCEPTED or FAILURE_REQUESTED delivery blocks the change; an open offer is expired and re-offered through the delivery service.
- **Refunds (DDR-114 (6)):** read-only; exceptional refunds stay disabled (DDR-44 open).
- **Audit (DDR-114 (7)):** an RM sees events of their regions; a CA sees all, including unscoped events. Date ranges default to the last 7 days and may be at most 31 days.
- **Exports (DDR-114 (8)):** orders and audit only, at most 5,000 rows, formula-leading text neutralised, and each export is itself audited (`management.export.*`).
- **Overview (DDR-114 (10)):** order counts by status, overdue incoming orders, pending approvals and each kitchen's intake state. A kitchen without capacity settings is shown as not configured, never guessed.

## Assumptions and integration points

- The 31-day range and 50-row page are UI bounds (#10 §14), not business values.
- WebSocket scope (region topics, RM own regions, CA all) is tested in `realtime/tests` (DDR-114 (13), DDR-115 (5)).
- No migration was needed for 10A (see Tables); DDR-114 (1) was updated to say so (2026-11-12).
