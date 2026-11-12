#!/usr/bin/env bash
# Runs once, on first initialisation of an empty data volume (official image behaviour).
# Creates the DB roles from DOCKER_DEPLOYMENT_DESIGN §6.3 and the required extensions.
# Schemas and per-schema grants are created by migrations in Task 3.
# Passwords are passed as psql variables (:'name') so they are quoted safely and never echoed.
set -euo pipefail

roles=(
  "app_migrator:APP_MIGRATOR_PASSWORD"
  "app_api:APP_API_PASSWORD"
  "p1_sop:P1_SOP_PASSWORD"
  "p2_elt:P2_ELT_PASSWORD"
  "p3_synth:P3_SYNTH_PASSWORD"
  "rag_customer:RAG_CUSTOMER_PASSWORD"
  "rag_kitchen:RAG_KITCHEN_PASSWORD"
  "rag_management:RAG_MANAGEMENT_PASSWORD"
)

for entry in "${roles[@]}"; do
  role="${entry%%:*}"
  var="${entry##*:}"
  password="${!var:-}"
  if [[ -z "$password" ]]; then
    echo "init: missing required variable $var" >&2
    exit 1
  fi
  psql -v ON_ERROR_STOP=1 -v role="$role" -v pw="$password" \
       --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE', :'role', :'pw') \gexec
SQL
  echo "init: created role $role"
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- Every role may connect; nothing else is granted here.
SELECT format('GRANT CONNECT ON DATABASE %I TO app_migrator, app_api, p1_sop, p2_elt, p3_synth, rag_customer, rag_kitchen, rag_management', current_database()) \gexec

-- Only the migrator runs DDL: it may create schemas and the alembic_version table.
SELECT format('GRANT CREATE ON DATABASE %I TO app_migrator', current_database()) \gexec
GRANT CREATE ON SCHEMA public TO app_migrator;
SQL
echo "init: extensions postgis, vector ready"
