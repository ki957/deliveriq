-- Real dishes only; TEST dishes never enter real models (DDR-48).
select m.id as menu_item_id, m.kitchen_id, m.name, c.name as category, m.price_paise, m.publication_status
from {{ source('app', 'menu_items') }} m
left join {{ source('app', 'menu_categories') }} c on c.id = m.category_id
where not m.is_test_fixture
