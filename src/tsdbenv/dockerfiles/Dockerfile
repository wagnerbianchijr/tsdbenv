# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19
# Dockerfile for PostgreSQL + TimescaleDB environment with Tiger Cloud extensions

ARG PG_VERSION=14
ARG BASE_IMAGE=timescale/timescaledb-ha:pg14

FROM ${BASE_IMAGE}

ARG PG_VERSION
ARG TS_VERSION

# The HA tag pins the requested PostgreSQL patch release. Build the selected
# TimescaleDB release because upstream does not publish every PG patch × TSDB
# release combination (for example, PG 15.18 with TSDB 2.14.2).
USER root
RUN set -eux; \
    pg_major="${PG_VERSION%%.*}"; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential cmake git libssl-dev "postgresql-server-dev-${pg_major}"; \
    git clone --depth 1 --branch "${TS_VERSION}" \
        https://github.com/timescale/timescaledb.git /tmp/timescaledb; \
    cd /tmp/timescaledb; \
    ./bootstrap -DCMAKE_BUILD_TYPE=Release -DREGRESS_CHECKS=OFF \
        -DTAP_CHECKS=OFF -DWARNINGS_AS_ERRORS=OFF \
        -DPROJECT_INSTALL_METHOD=docker-ha; \
    cmake --build build --parallel "$(nproc)"; \
    cmake --install build; \
    rm -rf /tmp/timescaledb /var/lib/apt/lists/*

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
