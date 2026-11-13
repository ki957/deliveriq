# Menu module (publication and customer menu read)

**Purpose and scope:** menu publication by RM and CA (DDR-11, DDR-31, DDR-107) and the public, read-only customer menu (PUBLISHED items only). Dish availability requests and decisions are here too (Task 8A; KI-24, DDR-111 (7)). Filters, cart and checkout are Task 6. The publish UI is Task 5C; the availability UI Task 8B.

| Item | Value |
|---|---|
| UI screens | Management → Menu publication (Task 5C); Customer menu (Task 6) |
| API endpoints | Public: `GET /api/v1/menu/items` · Management: `GET /api/v1/menu/manage/items` · `POST /api/v1/menu/manage/items/{id}/transitions` (`mark_ready`, `publish`) · Availability: `GET /api/v1/menu/availability/dishes?kitchen_id=` · `GET/POST /api/v1/menu/availability/requests` · `POST /api/v1/menu/availability/requests/{id}/decision` |
| Service functions | `customer_menu`, `list_items`, `transition`; `kitchen_dishes`, `request_availability`, `availability_requests`, `decide_availability` |
| Tables | `app.menu_items`, `app.menu_categories`, `app.recipe_versions` (ACTIVE check), `audit.menu_publications` (written by trigger), `app.dish_availability_requests`, `audit.events` |
| Permissions | `menu.publish`: CA any region, RM assigned regions only. Everyone else 403; another region's item is 404. Availability: `kitchen.unavailability.request` (KS, KM own kitchen) to request; `management.unavailability.approve` (RM own region, CA) to decide; the kitchen can never decide (403) |
| States | 200 · 401 · 403 · 404 · 409 wrong step or readiness missing (the message lists the missing fields) |
| Tests | `tests/test_domain.py` (unit); `recipes/tests/test_workflow_integration.py` (authority, readiness, audit, customer visibility) |

## Rules implemented

- **Authority (DDR-31):** checked in the service and by the database transition table; an RM outside the assigned region is refused even when calling directly.
- **Readiness (DDR-11):** the `check_menu_readiness` trigger requires an ACTIVE recipe version and every readiness field for `READY_FOR_PUBLICATION` and `PUBLISHED`; steps cannot be skipped.
- **Audit (DDR-31):** every status change writes `audit.menu_publications` with actor, role, region, time, item and action.
- **Dish availability (KI-24; DDR-111 (7)):** the kitchen asks to make a published dish unavailable, or to bring it back, with a reason; one pending request per dish. RM (own region) or CA approves (the menu status changes, reason recorded, readiness re-checked on the way back) or rejects with a reason. Only an approval reaches the customer menu. Requests and decisions are audited.
- **Customer view:** only `PUBLISHED` items; in production, fixture items are filtered too (plan §5.2 control 4); TEST items carry `is_test_fixture` so every UI labels them.
