#!/bin/bash
# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19
# Wrapper script to initialize tsdbadmin user with password from environment variable

set -e

# Get password from environment variable (defaults to empty if not set)
PASSWORD="${TSDBADMIN_PASSWORD:-}"

# Execute init-tsdbadmin.sql with password variable passed via psql -v flag
psql -v ON_ERROR_STOP=1 -v password="$PASSWORD" <<'EOF'
-- Keep the standard PostgreSQL superuser available for on-premises testing.
ALTER ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';
-- Match the managed Tiger Cloud administrator role attributes.
CREATE ROLE tsdbadmin WITH LOGIN NOSUPERUSER CREATEDB CREATEROLE REPLICATION PASSWORD :'password';
-- Create default tsdb database owned by tsdbadmin
CREATE DATABASE tsdb OWNER tsdbadmin;
-- Set default search_path for tsdbadmin
ALTER ROLE tsdbadmin SET search_path = public, pg_catalog;
EOF

# Connect to tsdb and create extensions
psql -v ON_ERROR_STOP=1 -d tsdb -U postgres <<'EOF'
-- Create TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
-- Create postgres_fdw for remote connections
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
-- Create pg_buffercache for buffer analysis
CREATE EXTENSION IF NOT EXISTS pg_buffercache;
-- Create pg_stat_statements for query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
-- Create Tiger Cloud-compatible analytics and vector extensions
CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
EOF
