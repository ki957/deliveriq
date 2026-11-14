"""Management reports support (Task 13; DDR-117 (6), (8)).

- `app_api` may use the `analytics` and `analytics_synthetic` schemas. Table access is granted by dbt itself
  (`grants` config) on marts and dimensions only, because dbt recreates its tables on every run; raw, staging
  and facts stay unreadable for the API.
- `ops.operational_totals()`: real (non-TEST) operational totals for the P2 reconciliation with operational
  tables (ETL spec §11.2). SECURITY DEFINER and counts only, so `p2_elt` gets no new table grants
  (DDR-116 (4)); the P2 run compares them with its facts and records each comparison as a critical check.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
GRANT USAGE ON SCHEMA analytics, analytics_synthetic TO app_api;

CREATE FUNCTION ops.operational_totals() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, app AS $$
    SELECT jsonb_build_object(
        'orders', (SELECT count(*) FROM app.orders WHERE NOT is_test_fixture),
        'orders_payable_paise', (SELECT coalesce(sum(payable_paise), 0) FROM app.orders WHERE NOT is_test_fixture),
        'payments_succeeded', (SELECT count(*) FROM app.payments WHERE NOT is_test_fixture AND method <> 'COD'
                                 AND status IN ('SUCCEEDED', 'REFUND_PENDING', 'REFUNDED')),
        'payments_failed', (SELECT count(*) FROM app.payments WHERE NOT is_test_fixture
                              AND status IN ('FAILED', 'TIMED_OUT')),
        'consumption_lines', (SELECT count(*) FROM app.stock_movements
                                WHERE kind = 'CONSUMPTION' AND NOT is_test_fixture),
        'deliveries_completed', (SELECT count(*) FROM app.delivery_assignments a
                                   JOIN app.orders o ON o.id = a.order_id
                                  WHERE a.status = 'COMPLETED' AND NOT o.is_test_fixture)
    )
$$;
REVOKE ALL ON FUNCTION ops.operational_totals() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.operational_totals() TO p2_elt;
"""

DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS ops.operational_totals();
REVOKE USAGE ON SCHEMA analytics, analytics_synthetic FROM app_api;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
