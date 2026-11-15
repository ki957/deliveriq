{{ config(grants={'select': ['app_api']}) }}  -- DDR-117 (6): dimensions are readable by the API
{% if var('dataset', 'analytics') == 'analytics_synthetic' %}
select (d.item->>'id')::uuid as menu_item_id, m.kitchen_id,
       d.item->>'name' as name, d.item->>'category' as category,
       (d.item->>'price_paise')::integer as price_paise,
       d.item->>'publication_status' as publication_status
from {{ source('synthetic', 'manifests') }} m
cross join lateral jsonb_array_elements(m.reference_data->'dishes') as d(item)
where m.profile = '{{ var('profile', 'demo') }}'
{% else %}
-- Real dishes only; TEST dishes never enter real models (DDR-48).
select m.id as menu_item_id, m.kitchen_id, m.name, c.name as category, m.price_paise, m.publication_status
from {{ source('app', 'menu_items') }} m
left join {{ source('app', 'menu_categories') }} c on c.id = m.category_id
where not m.is_test_fixture
{% endif %}
