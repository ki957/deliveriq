-- DDR-75 delivery performance: counts, summed durations and GPS km per day and kitchen (ETL §8.3; kitchen for
-- scope, DDR-117 (6)). Averages and targets wait for DDR-44.
select
    (coalesce(completed_at, failed_at, picked_up_at, assigned_at) at time zone 'Asia/Kolkata')::date as delivery_date,
    kitchen_id,
    min(region_id::text)::uuid as region_id,
    count(*) filter (where assigned_at is not null) as deliveries_assigned,
    count(*) filter (where completed_at is not null) as deliveries_completed,
    count(*) filter (where failed_at is not null) as deliveries_failed,
    sum(extract(epoch from completed_at - picked_up_at)) filter (where completed_at is not null) as delivery_seconds_total,
    sum(gps_km) as gps_km_total,
    sum(gps_simulated_points) as gps_simulated_points
from {{ ref('fact_deliveries') }}
group by 1, kitchen_id
