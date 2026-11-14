# Reports module (management analytics on the marts)

**Purpose and scope:** Management "Reports & Analytics" (#10 §10; MG-07, MG-08; plan Task 13; DDR-44, DDR-74, DDR-75, DDR-117). Reads the DDR-75 marts built by P2 (`analytics/dbt`) and shows the ETL spec §9 KPIs, each with its formula, source and "Definition pending approval (DDR-44)". Nothing is business truth (class A). Simulated data (`analytics_synthetic`) is Task 14.

| Item | Value |
| --- | --- |
| UI screens | `/management/reports` (`frontend/src/features/reports`) |
| API endpoints | `GET /api/v1/management/reports` (`dataset` analytics or analytics_synthetic, `date_from`, `date_to`, `kitchen_id`) · `GET /api/v1/management/reports.csv` (daily rows, audited `management.export.report`) |
| Code | `domain.py` (KPI list and formulas, periods, class-A constant), `repository.py` (mart reads; schema from a whitelist), `service.py` (scope, periods, CSV), `api.py` |
| Tables | Reads `analytics` (and later `analytics_synthetic`) marts and `dim_ingredient`; `app.kitchens` for scope; `ops.dataset_freshness`. `app_api` can read marts and dimensions only (dbt `grants`; migration 0016 gives schema usage); never raw, staging or facts |
| Permissions | `management.reports.view` (RM: kitchens of assigned regions; CA: all). An out-of-scope kitchen is 404 on the report and the CSV |
| States | 200 · 401 · 403 · 404 (kitchen outside scope) · 422 (range > 31 days, unknown dataset, export of a dataset not built) |
| Tests | `tests/test_domain.py` (4: class A stays off, formulas, no invented ratios, periods); `tests/test_reports_integration.py` (5: definition status and empty real data; scope RM/CA/others across report and CSV; bounds, whitelist, synthetic not built; scoped, labelled, audited CSV; the API role reads marts and dimensions only); E2E `reports.spec.ts` |

## Rules implemented

- **KPIs (DDR-117 (1), (2)):** 13 ETL spec §9 formulas over base measures. Rejection rate, completion rate and AOV use denominators chosen for the POC and say so. A KPI with a zero denominator has no value (MG-08).
- **Periods (DDR-117 (3)):** 7 days ending today (IST) by default, at most 31, compared with the previous period of the same length.
- **Real vs simulated (DDR-74, DDR-117 (4)):** separate datasets, never mixed. Real excludes TEST rows, so it is empty in this POC and the page says why; Simulated reads "Not built yet (Task 14)" until P3 builds it.
- **Not available (DDR-117 (5)):** customers, staff and promotions metrics have no source model and are listed with the reason.
- **Freshness (DDR-117 (11)):** "Data as of …" from `ops.dataset_freshness`; older than 24 h is a warning (labelled test default).
- **Export (DDR-117 (10)):** the daily view of the current filters, same scope, formula-injection guard, the dataset and definition status in the first row, audited.

## Assumptions and integration points

- Reports do not poll: the marts change only when P2 runs.
- Reconciliation with operational tables runs inside P2 (`pipelines/p2_elt/reconcile.py`, DDR-117 (8)).
