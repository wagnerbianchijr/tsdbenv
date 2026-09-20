# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19
# Dockerfile for PostgreSQL + TimescaleDB environment with Tiger Cloud extensions

ARG PG_VERSION=14

FROM timescale/timescaledb-ha:pg${PG_VERSION}

# The HA image includes TimescaleDB Toolkit and the broader extension set used by
# Tiger Cloud. The lightweight Alpine OSS image does not ship Toolkit binaries.

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
USER root
COPY init-tsdbadmin.sh /docker-entrypoint-initdb.d/01-init-tsdbadmin.sh
RUN chown postgres:postgres /docker-entrypoint-initdb.d/01-init-tsdbadmin.sh \
    && chmod 755 /docker-entrypoint-initdb.d/01-init-tsdbadmin.sh
USER postgres
