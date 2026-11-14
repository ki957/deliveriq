select id as ingredient_id, name, unit, origin from {{ source('app', 'ingredients') }} where origin <> 'TEST_FIXTURE'
