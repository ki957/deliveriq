-- One row per order that reached delivery; GPS figures are the per-delivery summary (DDR-78, DDR-113 (13)).
select
    order_id,
    min(region_id::text)::uuid as region_id,
    min(kitchen_id::text)::uuid as kitchen_id,
    min(occurred_at) filter (where event_type = 'delivery.assigned') as assigned_at,
    min(occurred_at) filter (where event_type = 'delivery.picked_up') as picked_up_at,
    min(occurred_at) filter (where event_type = 'delivery.completed') as completed_at,
    min(occurred_at) filter (where event_type = 'delivery.failed') as failed_at,
    max((data -> 'gps' ->> 'km')::numeric) as gps_km,
    max((data -> 'gps' ->> 'points')::integer) as gps_points,
    max((data -> 'gps' ->> 'duration_seconds')::integer) as gps_duration_seconds,
    max((data -> 'gps' ->> 'simulated_points')::integer) as gps_simulated_points,
    bool_or(is_test_fixture) as is_test_fixture
from {{ ref('stg_events') }}
where event_type like 'delivery.%'
group by order_id
