-- DDR-75 kitchen performance: counts and summed durations (seconds). Averages and targets wait for DDR-44.
select
    placed_date as service_date,
    kitchen_id,
    count(*) filter (where accepted_at is not null) as orders_accepted,
    count(*) filter (where rejected_at is not null) as orders_rejected,
    count(*) filter (where ready_at is not null) as orders_ready,
    sum(extract(epoch from accepted_at - placed_at)) filter (where accepted_at is not null) as accept_seconds_total,
    sum(extract(epoch from ready_at - accepted_at)) filter (where ready_at is not null) as prepare_seconds_total
from {{ ref('fact_orders') }}
group by placed_date, kitchen_id
