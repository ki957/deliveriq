-- DDR-75 daily sales. Base measures only (counts and paise sums); KPI formulas wait for DDR-44.
select
    placed_date as sales_date,
    kitchen_id,
    count(*) as orders_placed,
    count(*) filter (where delivered_at is not null) as orders_delivered,
    count(*) filter (where rejected_at is not null or cancelled_at is not null) as orders_rejected_or_cancelled,
    sum(payable_paise) as payable_paise,
    sum(discount_paise) as discount_paise,
    sum(payable_paise) filter (where delivered_at is not null) as delivered_payable_paise
from {{ ref('fact_orders') }}
group by placed_date, kitchen_id
