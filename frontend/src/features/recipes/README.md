# Recipes feature (Kitchen)

**Purpose and scope:** Kitchen recipes list and detail, the KM approval workflow and sign-offs, and the review queue (KI-17, KI-20; DDR-10, DDR-30, DDR-50, DDR-54, DDR-103, DDR-107, DDR-108). Recipe editing and versioning are not part of this task.

| Item          | Value                                                                                                                                                                                              |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI screens    | `/kitchen/recipes`, `/kitchen/recipes/:versionId`, `/kitchen/review-queue`                                                                                                                         |
| API endpoints | `GET /api/v1/recipes/versions`, `GET /api/v1/recipes/versions/{id}`, `POST …/transitions`, `POST …/signoffs`, `GET /api/v1/recipes/review-items`, `POST …/acknowledge` (generated client)          |
| Permissions   | `kitchen.recipes.view` and `kitchen.review.view` (KS, KM) for the screens. KM only: `kitchen.recipes.workflow` (actions), `kitchen.recipes.signoff` (four sign-offs), `kitchen.review.acknowledge` |
| States        | Loading, empty, error, denied, not found, success; inline reason/note forms with validation and the backend's refusal message                                                                      |
| Tests         | `recipes.test.tsx` (filters, KM actions and bodies, KS read-only, sign-offs, refusal messages, review queue); `tests/e2e/specs/recipes-workflow.spec.ts`                                           |

## Behaviour

- The UI offers only the steps that apply to the current status; the backend and the database decide (KM-only activation, five sign-offs, open review items, no SOP activation).
- Every step needs a reason, recorded in the audit history. Activation shows which sign-offs are missing.
- TEST recipes carry a "Test data" badge. SOP recipes show their lineage (file, SHA-256, lines, page) and any quarantine reason.
- Acknowledging a review item records a note; it never changes recipe data.
