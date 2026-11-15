{% macro generate_alias_name(custom_alias_name, node) -%}
    {%- set name = (custom_alias_name or node.name) | trim -%}
    {%- if var('dataset', 'analytics') == 'analytics_synthetic' and var('profile', 'demo') == 'ml' -%}
        ml_{{ name }}
    {%- else -%}
        {{ name }}
    {%- endif -%}
{%- endmacro %}
