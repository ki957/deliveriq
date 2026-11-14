-- Dates of the kitchen's time zone (Asia/Kolkata, #15 §2) that have events.
select distinct (occurred_at at time zone 'Asia/Kolkata')::date as date_day
from {{ ref('stg_events') }}
