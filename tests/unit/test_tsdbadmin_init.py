from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROLE_DEFINITION = (
    "CREATE ROLE tsdbadmin WITH LOGIN NOSUPERUSER CREATEDB CREATEROLE "
    "REPLICATION PASSWORD"
)
INIT_SCRIPTS = (
    PROJECT_ROOT / "src/tsdbenv/dockerfiles/init-tsdbadmin.sh",
    PROJECT_ROOT / "src/tsdbenv/dockerfiles/init-tsdbadmin.sql",
    PROJECT_ROOT / "src/tsdbenv/scripts/init-tsdbadmin.sql",
)


@pytest.mark.parametrize("script_path", INIT_SCRIPTS)
def test_tsdbadmin_role_matches_tiger_cloud(script_path):
    script = script_path.read_text()

    assert ROLE_DEFINITION in script
    assert "CREATE ROLE tsdbadmin WITH LOGIN SUPERUSER" not in script


@pytest.mark.parametrize("script_path", INIT_SCRIPTS)
def test_postgres_superuser_has_on_premises_test_credentials(script_path):
    script = script_path.read_text()

    assert "ALTER ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';" in script


def test_container_installs_and_enables_timescaledb_toolkit():
    dockerfile = (PROJECT_ROOT / "src/tsdbenv/dockerfiles/Dockerfile").read_text()
    init_script = (
        PROJECT_ROOT / "src/tsdbenv/dockerfiles/init-tsdbadmin.sh"
    ).read_text()

    assert "FROM ${BASE_IMAGE}" in dockerfile
    assert "timescaledb--${TS_VERSION}.sql" in dockerfile
    assert "timescaledb-${TS_VERSION}.so" in dockerfile
    assert "cmake --build" not in dockerfile
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit CASCADE;" in init_script


def test_container_installs_extensions_in_postgres_and_tsdb():
    init_script = (
        PROJECT_ROOT / "src/tsdbenv/dockerfiles/init-tsdbadmin.sh"
    ).read_text()

    assert "for database in postgres tsdb" in init_script
    assert 'psql -v ON_ERROR_STOP=1 -d "$database" -U postgres' in init_script
