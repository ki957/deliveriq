{{ config(grants={'select': ['app_api']}) }}  -- DDR-117 (6): dimensions are readable by the API
{% if var('dataset', 'analytics') == 'analytics_synthetic' %}
select m.region_id, m.reference_data->'region'->>'code' as code,
       m.reference_data->'region'->>'name' as name,
       m.reference_data->'region'->>'status' as status
from {{ source('synthetic', 'manifests') }} m
where m.profile = '{{ var('profile', 'demo') }}'
{% else %}
select id as region_id, code, name, status from {{ source('app', 'regions') }}
{% endif %}
