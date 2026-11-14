# dbt project: P2 staging, core and marts

**Purpose and scope:** the transformations of P2 (DATA_PIPELINE §5, §7, §8; DDR-74, DDR-75, DDR-116 (2)–(4), (7), (11), (12); ADR-DATA-002). dbt Core 1.12.7 with dbt-postgres 1.11.0 (worker group only), run by the P2 pipeline inside the worker as `p2_elt`, `threads` 2. Task 13 builds the management analytics on these marts; Task 14 builds `analytics_synthetic` with `--vars '{dataset: analytics_synthetic}'`.

| Item | Value |
| --- | --- |
| Run by | `backend/app/pipelines/p2_elt/pipeline.py` (stages dbt staging, core, marts, tests); mounted read-only at `/srv/analytics/dbt`; `target/` and `logs/` under `/tmp` |
| Connection | `profiles.yml` reads `DB_HOST`, `DB_PORT`, `POSTGRES_DB` and `DBT_P2_ELT_PASSWORD` from the environment; no secret in any file |
| Sources | `raw.events` (accepted, non-TEST events only); `app` reference tables by column (regions, kitchens without address or location, menu categories, menu items, ingredients) |
| Staging (`staging`) | `stg_events`: typed, one row per event id and per (type, idempotency key) |
| Core (`analytics`) | `dim_date`, `dim_region`, `dim_kitchen`, `dim_menu_item`, `dim_ingredient`; `fact_orders` (with `customer_key`), `fact_order_items`, `fact_payments`, `fact_inventory_movements`, `fact_kitchen_stage_events`, `fact_deliveries` |
| Marts (`analytics`) | `mart_daily_sales`, `mart_menu_performance`, `mart_kitchen_performance`, `mart_inventory_consumption`, `mart_delivery_performance`, `mart_payment_performance`: base measures only (counts, paise sums, summed durations, GPS km); every KPI is "definition pending approval" (DDR-44) |
| Tests (critical) | unique / not-null keys, relationships, `unique_combination` (mart grain), `reconcile_orders` (raw → fact → mart), `reconcile_inventory`, `zero_fixture_rows`. The run records warnings itself (raw freshness 24 h, outbox backlog 5 min; labelled test defaults) |

## Rules implemented

- **Deterministic and replay-safe:** every model is a full-rebuild table and staging deduplicates, so the same raw rows always give the same marts and a replay never double counts.
- **Real vs TEST and synthetic (DDR-48, DDR-74):** real models read non-TEST events only; `zero_fixture_rows` fails the run if any TEST row reaches a fact. Every order in this POC is TEST, so the real marts are empty (DDR-116 (7)).
- **Exact schemas:** `macros/generate_schema_name.sql` writes `staging` and `analytics` (or `analytics_synthetic` with the dataset var), never prefixed.
- **TEST fault input:** `reconciliation_offset` is set to 1 only by the local/test input `fault:reconciliation`, to prove a failed critical test fails the run and leaves the marts not fresh.

## Assumptions and integration points

- `order.placed` now carries its dish lines (`items`: dish id, quantity, charged unit price), needed by `fact_order_items` and `mart_menu_performance` (§8); older events have none.
- Times are converted to dates in Asia/Kolkata (#15 §2).
