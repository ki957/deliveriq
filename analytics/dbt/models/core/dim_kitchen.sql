-- No address or location: not granted and not needed (DDR-116 (4)).
select id as kitchen_id, code, region_id, name, status from {{ source('app', 'kitchens') }}
