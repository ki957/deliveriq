# Approvals feature (Management)

**Purpose and scope:** menu publication by RM and CA, and the product-owner recipe sign-off by a CA account (DDR-11, DDR-31, DDR-54, DDR-106–DDR-108). Dish unavailability (Task 8) and the full Menu & Inventory area (Task 10) are separate.

| Item          | Value                                                                                                                                                                                         |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI screens    | `/management/menu-publication`, `/management/recipe-signoff`, `/management/recipe-signoff/:versionId`                                                                                         |
| API endpoints | `GET /api/v1/menu/manage/items`, `POST /api/v1/menu/manage/items/{id}/transitions`, `GET /api/v1/recipes/versions`, `GET /api/v1/recipes/versions/{id}`, `POST …/signoffs` (generated client) |
| Permissions   | `menu.publish` (CA any region, RM assigned regions; scoped by the backend). `recipes.signoff.product_owner` (CA). Others see the denied state                                                 |
| States        | Loading, empty, error, denied, not found, success; the backend's readiness refusal is shown as an alert                                                                                       |
| Tests         | `approvals.test.tsx`; `tests/e2e/specs/recipes-workflow.spec.ts` (RM publishes the E2E recipe, CA signs, menu API shows it)                                                                   |

## Behaviour

- Only the next step is offered (mark ready from DRAFT, publish from READY); the database enforces readiness and the ACTIVE-recipe rule and writes the publication audit.
- TEST dishes carry a "Test data" badge; only TEST dishes are published in this POC (DDR-50).
- The sign-off list shows TEST recipes in validation only; the CA records the product-owner sign-off with a note.
