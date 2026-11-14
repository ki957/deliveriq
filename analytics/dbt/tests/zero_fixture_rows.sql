-- Critical (DDR-48 leak control; DATA_PIPELINE §7): no TEST fixture row reaches a real model.
{% set facts = ['fact_orders', 'fact_order_items', 'fact_payments', 'fact_inventory_movements',
                'fact_kitchen_stage_events', 'fact_deliveries'] %}
{% for f in facts %}
select '{{ f }}' as model, count(*) as fixture_rows from {{ ref(f) }} where is_test_fixture
having count(*) > 0
{% if not loop.last %}union all{% endif %}
{% endfor %}
