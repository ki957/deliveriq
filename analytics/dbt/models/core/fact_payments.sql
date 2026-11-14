select
    event_id,
    order_id,
    (data ->> 'payment_id')::uuid as payment_id,
    case event_type when 'payment.succeeded' then 'SUCCEEDED' else coalesce(data ->> 'status', 'FAILED') end as outcome,
    (data ->> 'amount_paise')::bigint as amount_paise,
    occurred_at,
    (occurred_at at time zone 'Asia/Kolkata')::date as payment_date,
    region_id,
    kitchen_id,
    is_test_fixture
from {{ ref('stg_events') }}
where event_type in ('payment.succeeded', 'payment.failed')
