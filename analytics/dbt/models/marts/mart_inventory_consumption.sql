-- DDR-75 inventory consumption per day, kitchen and ingredient (in the ingredient's unit).
select
    movement_date,
    kitchen_id,
    ingredient_id,
    sum(quantity) filter (where movement = 'consumed') as consumed_quantity,
    sum(quantity) filter (where movement = 'reserved') as reserved_quantity,
    sum(quantity) filter (where movement = 'released') as released_quantity
from {{ ref('fact_inventory_movements') }}
group by movement_date, kitchen_id, ingredient_id
