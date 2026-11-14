{{ config(grants={'select': ['app_api']}) }}  -- DDR-117 (6): dimensions are readable by the API
select id as ingredient_id, name, unit, origin from {{ source('app', 'ingredients') }} where origin <> 'TEST_FIXTURE'
