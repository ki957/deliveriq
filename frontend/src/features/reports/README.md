# Reports feature (Reports & Analytics)

**Purpose and scope:** the Management reports page (#10 §10; MG-07, MG-08, MG-U4; DDR-117). Backend: `reports` module.

| Item          | Value                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------ |
| UI screens    | `/management/reports`                                                                                                    |
| API endpoints | `GET /api/v1/management/reports` · `GET /api/v1/management/reports.csv` (generated client; CSV as a same-origin link)    |
| Permissions   | `management.reports.view` (RM own regions, CA all); hidden from the navigation without it                                |
| States        | Loading, error, denied, not found (kitchen outside scope), 422 reason (range), "Simulated data: Not built yet (Task 14)" |
| Tests         | `reports.test.tsx`; E2E `tests/e2e/specs/reports.spec.ts`                                                                |

## Behaviour

- Real and Simulated are separate tabs (`aria-pressed`), never mixed. The real tab states that every POC order is TEST, so its figures are empty.
- Filters: From, To (IST, at most 31 days), kitchen in scope. Export CSV downloads the same view.
- Each KPI card shows the value in its unit, the previous period and the change, the formula and source, the badge "Definition pending approval (DDR-44)" and, where chosen, the denominator note. A missing value reads "No value".
- Orders placed and delivered have a hand-written SVG sparkline with a text alternative (no chart library, DDR-117 (9)).
- The header shows freshness and, for a Central Administrator, a link to run P2.
