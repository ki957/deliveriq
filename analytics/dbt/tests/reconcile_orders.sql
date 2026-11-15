-- Critical (DATA_PIPELINE §7): every accepted real `order.placed` in raw is one row in fact_orders, and
-- the daily-sales mart counts the same orders. `reconciliation_offset` is only set by the TEST fault input.
{% set synthetic = var('dataset', 'analytics') == 'analytics_synthetic' %}
with r as (
    select count(distinct aggregate_id) as n from
    {{ source('synthetic', 'events') if synthetic else source('raw', 'events') }}
    where event_type = 'order.placed'
    {% if synthetic %}and profile = '{{ var('profile', 'demo') }}' and is_synthetic and is_test_fixture
    {% else %}and parse_status = 'accepted' and not is_test_fixture{% endif %}
),
f as (select count(*) + {{ var('reconciliation_offset') }} as n from {{ ref('fact_orders') }}),
m as (select coalesce(sum(orders_placed), 0) as n from {{ ref('mart_daily_sales') }})
select r.n as raw_orders, f.n as fact_orders, m.n as mart_orders
from r, f, m
where r.n <> f.n or f.n - {{ var('reconciliation_offset') }} <> m.n
