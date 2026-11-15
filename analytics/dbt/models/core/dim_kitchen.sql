{{ config(grants={'select': ['app_api']}) }}  -- DDR-117 (6): dimensions are readable by the API
-- No address or location: not granted and not needed (DDR-116 (4)).
{% if var('dataset', 'analytics') == 'analytics_synthetic' %}
select m.kitchen_id, m.reference_data->'kitchen'->>'code' as code, m.region_id,
       m.reference_data->'kitchen'->>'name' as name,
       m.reference_data->'kitchen'->>'status' as status
from {{ source('synthetic', 'manifests') }} m
where m.profile = '{{ var('profile', 'demo') }}'
{% else %}
select id as kitchen_id, code, region_id, name, status from {{ source('app', 'kitchens') }}
{% endif %}
