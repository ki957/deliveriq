-- Typed, deduplicated events (DATA_PIPELINE §8). Real models read accepted, non-TEST events only (DDR-48,
-- DDR-74); rejected events stay in raw for the UI.
with ranked as (
    select
        e.event_id,
        e.event_type,
        e.occurred_at,
        e.aggregate_id as order_id,
        e.region_id,
        e.kitchen_id,
        e.data,
        e.is_test_fixture,
        e.landed_at,
        row_number() over (partition by e.event_type, e.idempotency_key order by e.landed_at, e.event_id) as n
    from {{ source('raw', 'events') }} e
    where e.parse_status = 'accepted' and not e.is_test_fixture
)
select event_id, event_type, occurred_at, order_id, region_id, kitchen_id, data, is_test_fixture, landed_at
from ranked
where n = 1
