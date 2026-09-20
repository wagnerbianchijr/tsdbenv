# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- TimescaleDB Toolkit is now installed from the official TimescaleDB HA image
  and enabled in the default `tsdb` database.
- Prebuilt PostgreSQL 14–18 images are published to GitHub Container Registry.
- `tsdbenv new --rebuild` explicitly refreshes a local image.

### Changed
- Extension initialization now fails immediately when a required extension
  cannot be created instead of silently leaving a partially configured database.
- Container creation now reuses a local image, pulls a prebuilt image on a cache
  miss, and builds locally only as a fallback.
- Compatibility data uses its 24-hour cache instead of refreshing on every
  `new` command.
- Readiness checks query the initialized database and required extensions rather
  than matching an early PostgreSQL log message.

## [1.1.0] - 2026-09-19

### Added
- Automatic loading of `.env` from the current working directory.
- `.env.example` with Docker as the default container engine.
- Regression coverage for environment loading and `tsdbadmin` role attributes.

### Changed
- `tsdbadmin` now matches Tiger Cloud's key administrator attributes:
  `NOSUPERUSER`, `CREATEROLE`, and `REPLICATION`.
- Exported environment variables take precedence over values loaded from `.env`.

### Fixed
- Initialization scripts are installed with permissions that allow PostgreSQL's
  entrypoint user to execute them.

### Testing
- 119 tests pass.
- 7 Podman-only integration tests skip when Podman is unavailable.

---

## [1.0.0] - 2026-08-20

### Added
- **Podman support** as optional container engine alongside Docker
  - `--engine docker|podman` CLI flag for explicit engine selection
  - `TSDBENV_ENGINE` environment variable for engine override (CLI > env > default)
  - Automatic socket path detection for both engines
  - Graceful test skip when Podman unavailable
  - Network mode configuration (Docker bridge vs Podman slirp4netns)
  - Full documentation in `docs/PODMAN.md`

- **Comprehensive test coverage**
  - 16 unit tests for engine selection logic and socket path resolution
  - 16 unit tests for CLI --engine option parsing
  - 9 unit tests for DockerClient engine parameter handling
  - 7 integration tests for real Podman container lifecycle
  - Total: 113+ tests with 80%+ code coverage

- **Code quality infrastructure**
  - Black code formatter with pinned version (24.1.1)
  - isort import sorter with black profile (5.13.2)
  - flake8 linter (7.0.0)
  - mypy static type checker (1.8.0)
  - pylint for additional linting (3.0.3)
  - bandit for security scanning (1.7.5)
  - GitHub Actions CI/CD workflow for all checks

- **Developer experience**
  - Pinned dev tool versions in requirements.txt for consistency
  - pyproject.toml configuration for black and isort
  - Comprehensive inline documentation
  - CLAUDE.md for future contributors

### Fixed
- Docker regression: restored `docker.from_env()` for Docker engine to support DOCKER_HOST env var, Docker contexts, rootless Docker, and Colima
- Podman socket path: use rootless socket `/run/user/$UID/podman/podman.sock` instead of rootful `/run/podman/podman.sock`
- Type annotations: fixed mypy errors with explicit `DockerClient | None` type hints
- Formatting conflicts: resolved black/isort incompatibility with isort black profile

### Architecture
- **Engine abstraction layer** (`src/tsdbenv/engine_config.py`):
  - Single source of truth for engine-to-socket mapping
  - Enum-based engine selection
  - CLI/env precedence logic
  - EngineConfig dataclass for engine-specific settings

- **Docker client initialization** (`src/tsdbenv/docker_utils.py`):
  - Engine parameter passed to DockerClient
  - Conditional logic: `docker.from_env()` for Docker, explicit socket path for Podman
  - Clear error messages when engine unavailable

- **CLI integration** (`src/tsdbenv/cli.py`):
  - Global --engine option at Click group level
  - Engine context passed to all subcommands
  - CLIState reinitialization with selected engine

### Breaking Changes
None. Docker remains default, zero impact on existing workflows.

### Testing
- All 113+ tests pass
- 80%+ code coverage
- Podman integration tests skip gracefully if socket unavailable
- No CI failures on any test

### Documentation
- `README.md` — updated with --engine flag usage
- `docs/PODMAN.md` — 391 lines covering installation, setup, network modes, troubleshooting
- `CLAUDE.md` — developer guide for future maintainers
- Inline docstrings throughout codebase

---

## [0.1.0] - 2026-08-19

Initial release with Docker support, version compatibility matrix, and container lifecycle management.
