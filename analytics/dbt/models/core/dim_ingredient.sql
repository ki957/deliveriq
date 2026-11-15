{{ config(grants={'select': ['app_api']}) }}  -- DDR-117 (6): dimensions are readable by the API
{% if var('dataset', 'analytics') == 'analytics_synthetic' %}
select (i.item->>'id')::uuid as ingredient_id, i.item->>'name' as name,
       i.item->>'unit' as unit, i.item->>'origin' as origin
from {{ source('synthetic', 'manifests') }} m
cross join lateral jsonb_array_elements(m.reference_data->'ingredient_details') as i(item)
where m.profile = '{{ var('profile', 'demo') }}'
{% else %}
select id as ingredient_id, name, unit, origin from {{ source('app', 'ingredients') }}
where origin <> 'TEST_FIXTURE'
{% endif %}
