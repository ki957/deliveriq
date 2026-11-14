-- One row per placed order; lifecycle times from later events. Amounts are integer paise.
with placed as (
    select order_id, region_id, kitchen_id, occurred_at as placed_at, data, is_test_fixture
    from {{ ref('stg_events') }} where event_type = 'order.placed'
),
at_ as (
    select
        order_id,
        min(occurred_at) filter (where event_type = 'order.accepted') as accepted_at,
        min(occurred_at) filter (where event_type = 'order.ready_for_pickup') as ready_at,
        min(occurred_at) filter (where event_type = 'order.rejected') as rejected_at,
        min(occurred_at) filter (where event_type = 'order.cancelled') as cancelled_at,
        min(occurred_at) filter (where event_type = 'delivery.picked_up') as picked_up_at,
        min(occurred_at) filter (where event_type = 'delivery.completed') as delivered_at,
        min(occurred_at) filter (where event_type = 'delivery.failed') as delivery_failed_at
    from {{ ref('stg_events') }}
    group by order_id
)
select
    p.order_id,
    p.data ->> 'customer_key' as customer_key,
    p.region_id,
    p.kitchen_id,
    p.placed_at,
    (p.placed_at at time zone 'Asia/Kolkata')::date as placed_date,
    p.data ->> 'payment_method' as payment_method,
    (p.data ->> 'payable_paise')::bigint as payable_paise,
    coalesce((p.data ->> 'discount_paise')::bigint, 0) as discount_paise,
    (p.data ->> 'lines')::integer as line_count,
    a.accepted_at, a.ready_at, a.rejected_at, a.cancelled_at, a.picked_up_at, a.delivered_at,
    a.delivery_failed_at,
    p.is_test_fixture
from placed p
left join at_ a using (order_id)
