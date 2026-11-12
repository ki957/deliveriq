# Menu module (publication and customer menu read)

**Purpose and scope:** menu publication by RM and CA (DDR-11, DDR-31, DDR-107) and the public, read-only customer menu (PUBLISHED items only). Filters, cart and checkout are Task 6; unavailability is Task 8. The publish UI is Task 5C.

| Item | Value |
|---|---|
| UI screens | Management → Menu publication (Task 5C); Customer menu (Task 6) |
| API endpoints | Public: `GET /api/v1/menu/items` · Management: `GET /api/v1/menu/manage/items` · `POST /api/v1/menu/manage/items/{id}/transitions` (`mark_ready`, `publish`) |
| Service functions | `customer_menu`, `list_items`, `transition` |
| Tables | `app.menu_items`, `app.menu_categories`, `app.recipe_versions` (ACTIVE check), `audit.menu_publications` (written by trigger) |
| Permissions | `menu.publish`: CA any region, RM assigned regions only. Everyone else 403; another region's item is 404 |
| States | 200 · 401 · 403 · 404 · 409 wrong step or readiness missing (the message lists the missing fields) |
| Tests | `tests/test_domain.py` (unit); `recipes/tests/test_workflow_integration.py` (authority, readiness, audit, customer visibility) |

## Rules implemented

- **Authority (DDR-31):** checked in the service and by the database transition table; an RM outside the assigned region is refused even when calling directly.
- **Readiness (DDR-11):** the `check_menu_readiness` trigger requires an ACTIVE recipe version and every readiness field for `READY_FOR_PUBLICATION` and `PUBLISHED`; steps cannot be skipped.
- **Audit (DDR-31):** every status change writes `audit.menu_publications` with actor, role, region, time, item and action.
- **Customer view:** only `PUBLISHED` items; in production, fixture items are filtered too (plan §5.2 control 4); TEST items carry `is_test_fixture` so every UI labels them.
