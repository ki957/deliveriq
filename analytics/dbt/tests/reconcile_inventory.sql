-- Critical: every ingredient line of accepted real inventory events is one fact row.
with r as (
    select coalesce(sum(jsonb_array_length(coalesce(data -> 'lines', '[]'::jsonb))), 0) as n
    from {{ source('raw', 'events') }}
    where event_type like 'inventory.%' and parse_status = 'accepted' and not is_test_fixture
),
f as (select count(*) as n from {{ ref('fact_inventory_movements') }})
select r.n as raw_lines, f.n as fact_lines from r, f where r.n <> f.n
