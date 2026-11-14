{#- Exact schema names (`staging`, `analytics`), never prefixed (DATA_PIPELINE §3). With
    `--vars '{dataset: analytics_synthetic}'` (Task 14) the same models build `analytics_synthetic` instead,
    so real and synthetic rows never share a table (DDR-74). -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set name = (custom_schema_name or target.schema) | trim -%}
    {%- if name == 'analytics' and var('dataset', 'analytics') == 'analytics_synthetic' -%}
        analytics_synthetic
    {%- else -%}
        {{ name }}
    {%- endif -%}
{%- endmacro %}
