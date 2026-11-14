{{ config(grants={'select': ['app_api']}) }}  -- DDR-117 (6): dimensions are readable by the API
select id as region_id, code, name, status from {{ source('app', 'regions') }}
