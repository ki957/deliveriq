-- DDR-75 menu performance: dish quantities and paise per day. KPI formulas wait for DDR-44.
select
    i.placed_date as sales_date,
    i.kitchen_id,
    i.menu_item_id,
    m.name as menu_item_name,
    count(distinct i.order_id) as orders,
    sum(i.quantity) as quantity,
    sum(i.line_paise) as line_paise
from {{ ref('fact_order_items') }} i
left join {{ ref('dim_menu_item') }} m using (menu_item_id)
group by i.placed_date, i.kitchen_id, i.menu_item_id, m.name
