# Reports module (management analytics on the marts)

P3 (DDR-118) publishes validated demo marts in `analytics_synthetic`; the existing Simulated dataset then serves the same scoped KPIs and CSV, with `generated_from`/`generated_to` for the UI's explicit demo-date action. A failed rebuild removes synthetic freshness and makes this dataset unavailable until validation succeeds.

**Purpose and scope:** Management "Reports & Analytics" (#10 §10; MG-07, MG-08; plan Tasks 13 and 18; DDR-44, DDR-74, DDR-75, DDR-117, DDR-124). Reads the DDR-75 marts built by P2 (`analytics/dbt`) and shows the ETL spec §9 KPIs, each with its formula, source and "Definition pending approval (DDR-44)". Task 18 adds a read-only demand advisory from the `analytics_synthetic.ml_*` relations after the immutable P3 `ml` profile is ready. Forecasts are generated on request, labelled as simulated and advisory, and are never inventory actions.

| Item | Value |
| --- | --- |
| UI screens | `/management/reports` (`frontend/src/features/reports`) |
| API endpoints | `GET /api/v1/management/reports` (`dataset` analytics or analytics_synthetic, `date_from`, `date_to`, `kitchen_id`) · `GET /api/v1/management/reports.csv` (daily rows, audited `management.export.report`) · `GET /api/v1/management/reports/forecast` (optional in-scope `kitchen_id`) |
| Code | `domain.py` (KPI list and formulas, periods, class-A constant), `repository.py` (mart reads; fixed schema names), `forecasting.py` (stdlib seasonal model and backtest), `service.py` (scope and on-request forecast), `api.py` |
| Tables | Existing reports read `analytics`/`analytics_synthetic` marts and dimensions; forecast reads only `analytics_synthetic.ml_mart_inventory_consumption` and `ml_dim_ingredient`, with ML readiness from `ops.synthetic_status()` (SECURITY DEFINER). `app_api` has dbt-granted SELECT on marts and dimensions; never raw, staging, facts, inventory or operational orders |
| Permissions | `management.reports.view` (RM: kitchens of assigned regions; CA: all). An out-of-scope kitchen is 404 on the report and the CSV |
| States | 200 · 401 · 403 · 404 (kitchen outside scope) · 422 (range > 31 days, unknown dataset, export of a dataset not built) |
| Tests | `tests/test_domain.py` (4: class A stays off, formulas, no invented ratios, periods); `tests/test_forecasting.py` (3: weekday mean, strict baseline gate and origin isolation); `tests/test_reports_integration.py` (6: report definitions; role/kitchen scope; bounds and dataset labels; audited CSV; forecast readiness, scope and baseline; mart-only API access); E2E `reports.spec.ts` |

## Rules implemented

- **KPIs (DDR-117 (1), (2)):** 13 ETL spec §9 formulas over base measures. Rejection rate, completion rate and AOV use denominators chosen for the POC and say so. A KPI with a zero denominator has no value (MG-08).
- **Periods (DDR-117 (3)):** 7 days ending today (IST) by default, at most 31, compared with the previous period of the same length.
- **Real vs simulated (DDR-74, DDR-117 (4)):** separate datasets, never mixed. Real excludes TEST rows, so it is empty in this POC and the page says why; Simulated reads "Not built yet (Task 14)" until P3 builds it.
- **Demand forecast (DDR-124):** daily ingredient consumption for seven days from the ready immutable P3 ML profile. The weekday-seasonal mean must beat the same-weekday previous-week baseline by macro-averaged MAE over two rolling seven-day windows. If the profile is not ready or the model does not pass, no forecasts are returned. CA/RM only; existing report scope applies; results are simulated, advisory and read-only.
- **Not available (DDR-117 (5)):** customers, staff and promotions metrics have no source model and are listed with the reason.
- **Freshness (DDR-117 (11)):** "Data as of …" from `ops.dataset_freshness`; older than 24 h is a warning (labelled test default).
- **Export (DDR-117 (10)):** the daily view of the current filters, same scope, formula-injection guard, the dataset and definition status in the first row, audited.

## Assumptions and integration points

- Reports do not poll: the marts change only when P2 runs.
- Reconciliation with operational tables runs inside P2 (`pipelines/p2_elt/reconcile.py`, DDR-117 (8)).
