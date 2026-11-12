# Recipes module (approval workflow, sign-offs, review queue)

**Purpose and scope:** the recipe approval workflow, the five release sign-offs and the SOP review queue (DDR-10, DDR-30, DDR-50, DDR-54, DDR-103, DDR-105–DDR-107). Activation is demonstrated on TEST recipes only; no SOP recipe is ever activated. The Kitchen UI is Task 5C.

| Item | Value |
|---|---|
| UI screens | Kitchen → Recipes, Review queue (Task 5C) |
| API endpoints | `GET /api/v1/recipes/versions?status=` · `GET /api/v1/recipes/versions/{id}` (fields, ingredients, lineage, sign-offs, missing sign-offs, review items) · `POST /api/v1/recipes/versions/{id}/transitions` (`submit`, `return`, `validate`, `reject`, `activate`; reason required) · `POST /api/v1/recipes/versions/{id}/signoffs` · `GET /api/v1/recipes/review-items?status=` · `POST /api/v1/recipes/review-items/{id}/acknowledge` (note required) |
| Service functions | `list_versions`, `version_detail`, `review_items`, `transition`, `record_signoff`, `acknowledge` |
| Tables | `app.recipes`, `app.recipe_versions`, `app.recipe_ingredients`, `app.recipe_signoffs`, `app.recipe_review_items`, `app.status_history`, `audit.events` |
| Permissions | KM (own kitchen): `kitchen.recipes.workflow`, `kitchen.recipes.activate`, `kitchen.recipes.signoff` (CHEF, FOOD_SAFETY_LEAD, INVENTORY_OWNER, KITCHEN_MANAGER), `kitchen.review.acknowledge`. KS and KM: `kitchen.recipes.view`, `kitchen.review.view`. CA: `recipes.signoff.product_owner` (also reads TEST recipes to sign). Everyone else 403 |
| States | 200/204 · 401 · 403 role or CSRF · 404 other kitchen or unknown · 409 illegal step, open review items, missing sign-offs, SOP recipe, duplicate sign-off · 422 missing reason or note |
| Tests | `tests/test_domain.py`, `core/tests/test_permissions.py` (unit); `tests/test_workflow_integration.py` (HTTP + DB) |

## Rules implemented

- **KM-only activation (DDR-30):** checked by the service and again by the database transition table (`allowed_roles`).
- **Five sign-offs (DDR-10, DDR-54, DDR-106):** activation is refused while any is missing; recording all five does not activate. Sign-offs are recorded once, during `PENDING_VALIDATION` or `VALIDATED`, on TEST recipes only.
- **Submission blocks:** quarantined duplicates have no transitions (DDR-13); open review items block `submit` (DDR-103), in the service and by trigger.
- **No SOP activation (DDR-50):** refused by the service and by the `recipe_versions_poc_no_sop_activation` constraint.
- **Audit:** every transition writes `app.status_history` (actor, role, time, reason) and `audit.events`; sign-offs and acknowledgements write `audit.events`.

## Assumptions and integration points

- Sign-off timing (during validation) is an implementation choice; the sources only require the five records before activation.
- Versioning (a new version superseding an ACTIVE one) and `DISABLED` are not exposed yet; no task has needed them.
