-- DDR-75 payment performance: outcomes and paise by day and method.
select
    p.payment_date,
    o.payment_method,
    count(*) filter (where p.outcome = 'SUCCEEDED') as payments_succeeded,
    count(*) filter (where p.outcome <> 'SUCCEEDED') as payments_failed,
    sum(p.amount_paise) filter (where p.outcome = 'SUCCEEDED') as succeeded_paise
from {{ ref('fact_payments') }} p
left join {{ ref('fact_orders') }} o using (order_id)
group by p.payment_date, o.payment_method
