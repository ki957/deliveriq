select
    event_id,
    order_id,
    kitchen_id,
    region_id,
    split_part(event_type, '.', 2) as stage,
    occurred_at,
    (occurred_at at time zone 'Asia/Kolkata')::date as stage_date,
    is_test_fixture
from {{ ref('stg_events') }}
where event_type in ('order.accepted', 'order.preparing', 'order.ready_for_pickup', 'order.rejected')
