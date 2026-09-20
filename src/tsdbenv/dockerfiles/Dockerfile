# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19
# Dockerfile for PostgreSQL + TimescaleDB environment with Tiger Cloud extensions

ARG PG_VERSION=14

FROM timescale/timescaledb:latest-pg${PG_VERSION}-oss

# TimescaleDB extension is pre-configured in the base image
# Built-in extensions available: pg_buffercache, pg_stat_statements, postgres_fdw
# Note: pgvector and vectorscale require additional packages not in standard repos
# timescaledb_toolkit is available in timescale images

# Set environment variables for postgres user
ENV POSTGRES_USER=postgres

# Expose PostgreSQL port
EXPOSE 5432

# Health check to verify PostgreSQL readiness
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD psql -U postgres -c "SELECT 1" || exit 1

# Copy initialization script to docker-entrypoint-initdb.d/
# This script executes automatically when PostgreSQL starts for the first time
# Use wrapper script to handle password variable substitution
COPY init-tsdbadmin.sh /docker-entrypoint-initdb.d/01-init-tsdbadmin.sh
RUN chmod 755 /docker-entrypoint-initdb.d/01-init-tsdbadmin.sh
