-- DDR-75 payment performance: outcomes and paise by day, kitchen and method (kitchen for scope, DDR-117 (6)).
select
    p.payment_date,
    p.kitchen_id,
    o.payment_method,
    count(*) filter (where p.outcome = 'SUCCEEDED') as payments_succeeded,
    count(*) filter (where p.outcome <> 'SUCCEEDED') as payments_failed,
    sum(p.amount_paise) filter (where p.outcome = 'SUCCEEDED') as succeeded_paise
from {{ ref('fact_payments') }} p
left join {{ ref('fact_orders') }} o using (order_id)
group by p.payment_date, p.kitchen_id, o.payment_method
