#!/bin/sh
set -eu
app_password="$(cat /run/secrets/pg_app)"
psql -v ON_ERROR_STOP=1 -U postgres --dbname postgres --set=app_password="$app_password" <<'SQL'
CREATE ROLE n8n_app LOGIN PASSWORD :'app_password';
CREATE DATABASE n8n OWNER n8n_app;
REVOKE ALL ON DATABASE n8n FROM PUBLIC;
SQL
