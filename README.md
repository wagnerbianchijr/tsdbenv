# tsdbenv

PostgreSQL + TimescaleDB environment manager via container. Spin up isolated local database environments with one command.

![PostgreSQL 18+](https://img.shields.io/badge/PostgreSQL-18%2B-336791?logo=postgresql&logoColor=white)
![TimescaleDB 2.29.0+](https://img.shields.io/badge/TimescaleDB-2.29.0%2B-0A1A29?logo=timescale&logoColor=white)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776ab?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker&logoColor=white)
![Podman](https://img.shields.io/badge/Podman-Supported-892CA0?logo=podman&logoColor=white)
![License MIT](https://img.shields.io/badge/License-MIT-green)

## Overview

**tsdbenv** simplifies local PostgreSQL + TimescaleDB development by automating container setup. Provide versions, validate compatibility, build and run isolated Docker containers with persistent state, automatic port assignment, and easy access to logs. Includes all Tiger Cloud extensions (TimescaleDB, pgvector, postgres_fdw, and more).

## Requirements

- **Docker** (installed and running) or **Podman** (rootless mode)
- **Python 3.8+**
- **Git** (for installer script)

## Installation

### Quick Install (One Command)

```bash
curl https://raw.githubusercontent.com/wagnerbianchijr/tsdbenv/main/install.sh | bash
```

*Homebrew*, see [INSTALL.md](INSTALL.md).

## Quick Start

Create a PostgreSQL 14 + TimescaleDB 2.10.0 container:

```bash
tsdbenv new --postgres 14 --timescaledb 2.10.0 --bind-ip 127.0.0.1
```

Output:
```
Container 'tsdb-abc12345' created successfully!

Connect:
  psql "postgresql://tsdbadmin:aBcD1234eFgH5678@127.0.0.1:5433/tsdb"  -- tiger cloud environment
  psql "postgresql://postgres:postgres@127.0.0.1:5433/tsdb"           -- on-premises environment
```

Copy and paste the connection string directly.

## Container Engine Selection

By default, tsdbenv uses Docker. To use Podman instead, specify `--engine podman`:

```bash
tsdbenv -n --engine podman --postgres 15 --timescaledb 2.10.0
```

Set via environment variable to avoid repeating the flag:

```bash
export TSDBENV_ENGINE=podman
tsdbenv -n --postgres 15 --timescaledb 2.10.0
```

**Requirements**: Podman must be installed and configured in rootless mode. Rootless Podman uses slirp4netns for port binding, which may add slight latency compared to Docker's host bridge mode.

**macOS Setup**: On macOS, use Podman Machine:

```bash
# Initialize and start Podman machine
podman machine init
podman machine start

# Podman Machine socket is auto-detected — no DOCKER_HOST needed!
tsdbenv -n --engine podman --postgres 15 --timescaledb 2.28.3
```

**Switching between Docker and Podman**:

⚠️ **Important**: `DOCKER_HOST` environment variable can interfere with Docker if set to Podman socket.

```bash
# Use Docker (default)
unset DOCKER_HOST
export TSDBENV_ENGINE=docker
tsdbenv -l

# Use Podman
unset DOCKER_HOST  # Let Podman auto-detect socket
export TSDBENV_ENGINE=podman
tsdbenv -l

# Or use -e flag to override per-command
tsdbenv -e docker -l  # Use Docker this command
tsdbenv -e podman -l  # Use Podman this command
```

**Legacy persistent setup** (only if needed):
```bash
# Not recommended — let auto-detection handle it
# export DOCKER_HOST="$(podman info --format '{{.Host.RemoteSocket.Path}}')"
```

## Commands

### new
Create a new PostgreSQL + TimescaleDB container.

```bash
tsdbenv new --postgres 14 --timescaledb 2.10.0 --bind-ip 127.0.0.1
```

**Options:**
- `--postgres VERSION` — PostgreSQL major or exact patch version (e.g., 15, 15.18)
- `--timescaledb VERSION` — Exact TimescaleDB release (e.g., 2.14.2)
- `--bind-ip IP` — IP to bind container to (default: 127.0.0.1)
- `--port PORT` — PostgreSQL port (auto-detected if not specified)
- `--config PATH` — PostgreSQL config file (optional)
- `--init PATH` — SQL file to execute after container creation
- `--tablespaces NAMES` — Comma-separated tablespace names to create
- `--force` — Skip version compatibility check
- `--rebuild` — Rebuild the local wrapper image instead of reusing it
- `--verbose` — Enable detailed logging with timestamps

**Features:**
- Auto-generates unique container names (`tsdb-{timestamp_hash}`)
- Auto-detects first available port (5432, 5433, 5434, ...)
- Validates PostgreSQL × TimescaleDB version compatibility
- Secure password generation (alphanumeric only)
- Creates a Tiger Cloud-compatible `tsdbadmin` role with the default `tsdb` database
- Configures `postgres`/`postgres` for on-premises testing
- Enables the complete extension set in both the `tsdb` and `postgres` databases

### Fast container creation

`tsdbenv` prepares images in fastest-first order:

1. Reuse the versioned `pg<postgres>-ts<timescaledb>` image when it exists locally.
2. Pull the exact PostgreSQL HA base image on a cache miss.
3. Build a small local wrapper that selects the packaged TimescaleDB release.

The first container for a PostgreSQL patch release may take longer while its HA
base image downloads. The CLI displays an animated elapsed-time counter during
image preparation and PostgreSQL startup. Later containers reuse the local
image for the same version pair.

PostgreSQL accepts a major version (such as `15`) or an exact patch release
(such as `15.18`). TimescaleDB accepts an exact release (such as `2.14.2`).
Local builds select that TimescaleDB release from the binaries packaged in the
selected PostgreSQL HA image, so historical TimescaleDB releases can be paired
with newer PostgreSQL patch releases without compiling from source:

```bash
tsdbenv new --postgres 15.18 --timescaledb 2.14.2 --bind-ip 127.0.0.1 --force
```

Use `--rebuild` after changing the Dockerfile or initialization scripts:

```bash
tsdbenv new --postgres 15 --timescaledb 2.11.0 --rebuild
```

Compatibility data is cached for 24 hours. Container readiness is reported only
after PostgreSQL has created the `tsdb` database and all required extensions in
both `tsdb` and `postgres`, including `timescaledb_toolkit`.

### list
List all containers.

```bash
tsdbenv list
```

Output:
```
Name            PG    TSDB       IP              Port   Engine  
-----------------------------------------------------------------
tsdb-04d30960   14    2.10.0     127.0.0.1       5433   docker  
tsdb-abcd1234   15    2.11.0     127.0.0.1       5434   podman  
```

### logs
Show container logs.

```bash
tsdbenv logs
```

Select container interactively. Shows PostgreSQL startup logs and readiness status.

### remove
Remove a container.

```bash
tsdbenv remove tsdb-04d30960
tsdbenv -r tsdb-04d30960
```

Confirmation required. Gracefully handles containers no longer in Docker.

### removeall
Remove all containers at once.

```bash
tsdbenv removeall
tsdbenv -a
```

Lists all containers and prompts for confirmation before removing. Useful for cleaning up after testing.

**Options:**
- `--force` — Skip confirmation prompt (dangerous, use with care)

```bash
# With confirmation (default)
tsdbenv -a

# Skip confirmation (requires --force)
tsdbenv removeall --force
```

### connectstring
Get both psql commands for a container.

```bash
tsdbenv connectstring tsdb-04d30960
```

Example output:

```text
psql "postgresql://tsdbadmin:aBcD1234eFgH5678@127.0.0.1:5433/tsdb"  -- tiger cloud environment
psql "postgresql://postgres:postgres@127.0.0.1:5433/tsdb"           -- on-premises environment
```

### versionrefresh
Refresh TimescaleDB version compatibility matrix.

```bash
tsdbenv versionrefresh
```

Fetches latest compatibility data from Docker Hub, merges with fallback versions, caches locally. Runs automatically on `tsdbenv new`.

### matrix
Display PostgreSQL × TimescaleDB compatibility matrix as a formatted table.

```bash
tsdbenv matrix
```

Shows all supported PostgreSQL versions and their compatible TimescaleDB versions.

## Short Flags

All commands support dash-prefixed short flags for quick access:

```bash
tsdbenv -n --postgres 15 --timescaledb 2.10.0    # new
tsdbenv -l                                        # list
tsdbenv -r tsdb-04d30960                          # remove
tsdbenv -c tsdb-04d30960                          # connectstring
tsdbenv -a                                        # removeall (with confirmation)
tsdbenv -g                                        # versionrefresh (get versions)
tsdbenv -m                                        # matrix
tsdbenv -v                                        # version
tsdbenv -h                                        # help
tsdbenv -t "fast,archive"                         # tablespaces
```

**Combine multiple options:**

```bash
tsdbenv -n --postgres 16 \
  --timescaledb 2.29.2 \
  -t "fast,archive" \
  --init schema.sql
```

## Logging and Verbosity

By default, tsdbenv shows animated spinners and elapsed time for long-running
operations. Use `--verbose` for detailed timestamped logs:

```bash
# Default: clean output with spinner animation
tsdbenv new --postgres 16 --timescaledb 2.29.2 -i schema.sql

⠙ Loading TimescaleDB compatibility data... [00:01]
⠴ Preparing PostgreSQL 16 + TimescaleDB 2.29.2 image... [00:08]
⠦ Creating container tsdb-2af14423 and waiting for PostgreSQL... [00:04]
⠇ Executing init SQL file... [00:01]

Container 'tsdb-2af14423' created successfully!
```

```bash
# Verbose: detailed timestamped logs
tsdbenv new --postgres 16 --timescaledb 2.29.2 -i schema.sql --verbose

2026-09-23 10:31:18 Loading TimescaleDB compatibility data...
2026-09-23 10:31:19 Preparing PostgreSQL 16 + TimescaleDB 2.29.2 image...
2026-09-23 10:31:27 Creating container tsdb-2af14423 and waiting for PostgreSQL...
2026-09-23 10:31:31 Executing init SQL file...
2026-09-23 10:31:32 Init SQL executed successfully

Container 'tsdb-2af14423' created successfully!
```

Works with any subcommand:
```bash
tsdbenv --verbose new --postgres 16 --timescaledb 2.29.2
tsdbenv new --postgres 16 --timescaledb 2.29.2 --verbose  # Both syntaxes work
```

## Connection

All containers support two connection models:

- `tsdbadmin` uses a secure generated password and matches Tiger Cloud's key
  administrator attributes: `NOSUPERUSER`, `CREATEROLE`, and `REPLICATION`.
- `postgres` is a superuser with password `postgres` for on-premises testing.

- **Default database:** `tsdb`
- **Tiger Cloud user:** `tsdbadmin`
- **On-premises user:** `postgres`

Both connect to the `tsdb` database:

```bash
psql "postgresql://tsdbadmin:password@127.0.0.1:5433/tsdb"
psql "postgresql://postgres:postgres@127.0.0.1:5433/tsdb"
```

## Environment configuration

Copy the example configuration once:

```bash
cp .env.example .env
tsdbenv list
```

Every `tsdbenv` command automatically loads `.env` from the current directory.
The local file is ignored by Git, and an already-exported variable takes
precedence over its `.env` value. Currently supported:

- `TSDBENV_ENGINE=docker` selects Docker (the default).
- `TSDBENV_ENGINE=podman` selects Podman.

## Extensions

Containers include Tiger Cloud production extensions pre-installed and enabled:

- **timescaledb** — Time-series data, hypertables, continuous aggregates
- **vector** (pgvector) — Vector similarity search (AI/ML)
- **postgres_fdw** — Foreign data wrapper for remote PostgreSQL connections
- **pg_buffercache** — Buffer pool analysis and statistics
- **pg_stat_statements** — Query performance tracking
- **timescaledb_toolkit** — Advanced time-series analytics functions, installed
  from the official TimescaleDB HA image
- **plpgsql** — PL/pgSQL procedural language

The complete extension set is enabled in both the `tsdb` and `postgres`
databases so either connection model is ready for testing.

List extensions in container:

```bash
psql "postgresql://tsdbadmin:password@127.0.0.1:5433/tsdb" -c "\dx"
```

## Schema Preloading

Automatically load SQL schemas, fixtures, and sample data when creating containers.

**Create a schema file (schema.sql):**

```sql
CREATE TABLE metrics (
    time TIMESTAMPTZ NOT NULL,
    host TEXT NOT NULL,
    cpu FLOAT NOT NULL,
    memory INT NOT NULL
);

SELECT create_hypertable('metrics', 'time');

-- Insert sample data
INSERT INTO metrics VALUES
    (NOW(), 'server-1', 45.2, 2048),
    (NOW(), 'server-2', 62.1, 4096),
    (NOW(), 'server-3', 28.9, 1024);
```

**Create container with schema:**

```bash
tsdbenv -n --postgres 15 --timescaledb 2.10.0 --init schema.sql
```

**Use cases:**
- Load test schemas for integration testing
- Seed sample data for development
- Reproducible test environments
- Regression testing across PostgreSQL versions

## Tablespaces

Create and use custom tablespaces automatically during container creation.

**Automatic tablespace creation:**

```bash
# Create container with multiple tablespaces
tsdbenv -n --postgres 16 --timescaledb 2.29.2 --tablespaces "fast,archive,cold"

# Short flag
tsdbenv -n --postgres 16 --tablespaces "hot,warm,cold"
tsdbenv -n --postgres 16 -t "hot,warm,cold"
```

**Use tablespaces for performance testing:**

```bash
# Connect to container
psql "postgresql://tsdbadmin:password@127.0.0.1:5433/tsdb"

# Create table on specific tablespace
CREATE TABLE metrics_fast (
    time TIMESTAMPTZ,
    data FLOAT
) TABLESPACE fast;

SELECT create_hypertable('metrics_fast', 'time');

# List tablespaces
\db
```

**Features:**
- Automatic directory creation with proper permissions
- Full PostgreSQL integration (ready to use immediately)
- No manual `docker exec` or `chown` commands needed
- Perfect for testing storage performance characteristics

**Note:** Tablespaces are ephemeral — data is lost when the container stops. For persistent tablespaces, use a bind-mounted volume on the host.

## Examples

### Quick Examples

```bash
# Create container
$ tsdbenv -n --postgres 16 --timescaledb 2.29.2

# Create with init SQL and tablespaces
$ tsdbenv -n --postgres 16 --timescaledb 2.29.2 -t fast,archive -i schema.sql

# List existing containers
$ tsdbenv -l

# Get connection string
$ tsdbenv -c <container_name>

# Create tablespaces on container
$ tsdbenv -t <container_name> --tablespaces fast,archive

# Use Podman instead of Docker
$ tsdbenv -n --postgres 16 --engine podman

# Refresh version cache
$ tsdbenv -g

# Show the current compatibility matrix
$ tsdbenv -m
```

### Create and connect to a container

```bash
# Create PostgreSQL 15 + TimescaleDB 2.10.0
tsdbenv new --postgres 15 --timescaledb 2.10.0 --bind-ip 127.0.0.1

# Copy the connection string from output
psql "postgresql://tsdbadmin:ABC123def456@127.0.0.1:5433/tsdb"

# Create a hypertable
CREATE TABLE metrics (
  time TIMESTAMPTZ NOT NULL,
  host TEXT NOT NULL,
  cpu FLOAT NOT NULL
);

SELECT create_hypertable('metrics', 'time');
```

### List all running containers

```bash
tsdbenv list

# Output:
# Name            PG    TSDB       IP              Port   Engine  
# -----------------------------------------------------------------
# tsdb-04d30960   14    2.10.0     127.0.0.1       5433   docker  
# tsdb-b1a6b5e5   15    2.10.0     127.0.0.1       5435   podman  
```

### View container logs

```bash
tsdbenv logs

# Select container interactively
# Shows PostgreSQL startup logs and readiness status
```

### Remove a container

```bash
tsdbenv remove tsdb-04d30960

# Prompts for confirmation before removal
```

## Troubleshooting

### Podman Socket Not Found

**Error**: `Podman is not running or not installed. Install with: brew install podman`

**Solution**: On macOS with Podman Machine, set the `DOCKER_HOST` environment variable:

```bash
# Check running Podman machines
podman machine list

# Get the socket path (shown in machine output)
export DOCKER_HOST="unix:///var/folders/.../T/podman/podman-machine-default-api.sock"

# Verify connection
podman ps
```

### Port Already in Use

**Error**: `Port 5432 already in use`

**Solution**: tsdbenv auto-detects ports. If a specific port is in use, run without `--port` or specify an alternative:

```bash
# Let tsdbenv find an available port
tsdbenv new --postgres 16 --timescaledb 2.29.2

# Or specify an alternative port
tsdbenv new --postgres 16 --timescaledb 2.29.2 --port 5435
```

### Container Creation Fails

**Ensure**:
- Docker or Podman is running: `docker ps` or `podman ps`
- Sufficient disk space: `docker system df` or `podman system df`
- Network connectivity: check bind-ip is valid

**Debug**:
```bash
# View detailed logs
tsdbenv logs <container_name>

# Verify image exists
docker images | grep tsdbenv
```

## License

MIT
