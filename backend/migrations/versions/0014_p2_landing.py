"""P2 landing support (Task 12A; DATA_PIPELINE §12; DDR-116 (1), (6), (10)).

- `ops.outbox_backlog()`: unpublished outbox events, the oldest one's time, and landed / rejected raw
  counts, for the Data Pipelines overview. The API role cannot read the outbox or raw (ADR-DATA-003), so a
  narrow SECURITY DEFINER function returns counts and one timestamp only, never event content.
- A statement-level trigger on `app.outbox` sends a realtime `backlog` notice whenever events are written
  or landed, so the overview updates live (DDR-115 (4); CA only, filtered by the hub).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE FUNCTION ops.outbox_backlog()
RETURNS TABLE (waiting bigint, oldest_waiting_at timestamptz, landed bigint, rejected bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, app, raw AS $$
    SELECT (SELECT count(*) FROM app.outbox WHERE published_at IS NULL),
           (SELECT min(created_at) FROM app.outbox WHERE published_at IS NULL),
           (SELECT count(*) FROM raw.events WHERE parse_status = 'accepted'),
           (SELECT count(*) FROM raw.events WHERE parse_status = 'rejected')
$$;
REVOKE ALL ON FUNCTION ops.outbox_backlog() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.outbox_backlog() TO app_api;

CREATE FUNCTION app.rt_notify_backlog() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
    PERFORM pg_notify('deliveriq_rt',
        jsonb_build_object('k', 'backlog', 'id', '00000000-0000-0000-0000-000000000000')::text);
    RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION app.rt_notify_backlog() FROM PUBLIC;
CREATE TRIGGER z_rt_outbox AFTER INSERT OR UPDATE ON app.outbox
    FOR EACH STATEMENT EXECUTE FUNCTION app.rt_notify_backlog();
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS z_rt_outbox ON app.outbox;
DROP FUNCTION IF EXISTS app.rt_notify_backlog();
DROP FUNCTION IF EXISTS ops.outbox_backlog();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
