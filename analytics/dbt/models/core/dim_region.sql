select id as region_id, code, name, status from {{ source('app', 'regions') }}
