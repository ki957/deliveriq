-- Dish lines from `order.placed` (ids, quantities, charged unit price). Older events have no lines.
select
    e.order_id,
    (i ->> 'menu_item_id')::uuid as menu_item_id,
    (i ->> 'quantity')::integer as quantity,
    (i ->> 'unit_price_paise')::bigint as unit_price_paise,
    (i ->> 'quantity')::integer * (i ->> 'unit_price_paise')::bigint as line_paise,
    e.kitchen_id,
    (e.occurred_at at time zone 'Asia/Kolkata')::date as placed_date,
    e.is_test_fixture
from {{ ref('stg_events') }} e
cross join lateral jsonb_array_elements(coalesce(e.data -> 'items', '[]'::jsonb)) as i
where e.event_type = 'order.placed'
