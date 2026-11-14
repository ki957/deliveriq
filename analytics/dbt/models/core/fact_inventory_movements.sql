-- One row per ingredient line of a reservation, release or consumption.
select
    e.event_id,
    l.ordinality as line_no,
    e.order_id,
    e.kitchen_id,
    split_part(e.event_type, '.', 2) as movement,
    (l.value ->> 'ingredient_id')::uuid as ingredient_id,
    (l.value ->> 'quantity')::numeric as quantity,
    e.occurred_at,
    (e.occurred_at at time zone 'Asia/Kolkata')::date as movement_date,
    e.is_test_fixture
from {{ ref('stg_events') }} e
cross join lateral jsonb_array_elements(coalesce(e.data -> 'lines', '[]'::jsonb)) with ordinality as l(value, ordinality)
where e.event_type in ('inventory.reserved', 'inventory.released', 'inventory.consumed')
