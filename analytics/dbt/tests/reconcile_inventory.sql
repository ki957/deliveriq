-- Critical: every ingredient line of accepted real inventory events is one fact row.
{% set synthetic = var('dataset', 'analytics') == 'analytics_synthetic' %}
with r as (
    select coalesce(sum(jsonb_array_length(coalesce(data -> 'lines', '[]'::jsonb))), 0) as n
    from {{ source('synthetic', 'events') if synthetic else source('raw', 'events') }}
    where event_type like 'inventory.%'
    {% if synthetic %}and profile = '{{ var('profile', 'demo') }}' and is_synthetic and is_test_fixture
    {% else %}and parse_status = 'accepted' and not is_test_fixture{% endif %}
),
f as (select count(*) as n from {{ ref('fact_inventory_movements') }})
select r.n as raw_lines, f.n as fact_lines from r, f where r.n <> f.n
