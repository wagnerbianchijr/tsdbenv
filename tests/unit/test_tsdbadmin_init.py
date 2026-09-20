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
    assert "LOGIN SUPERUSER" not in script
