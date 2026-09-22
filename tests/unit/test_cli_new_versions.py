from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tsdbenv import cli
from tsdbenv.docker_utils import DockerClient


def test_new_uses_exact_postgres_and_timescaledb_releases():
    state = MagicMock()
    state.engine.value = "docker"
    state.version_manager.is_compatible.return_value = True
    state.docker_client.create_container.return_value = "container-123"
    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.new,
            [
                "--postgres",
                "15.18",
                "--timescaledb",
                "2.14.2",
                "--bind-ip",
                "127.0.0.1",
                "--port",
                "55432",
                "--force",
            ],
        )

    assert result.exit_code == 0, result.output
    kwargs = state.docker_client.prepare_image.call_args.kwargs
    assert kwargs["tag"] == "ghcr.io/wagnerbianchijr/tsdbenv:pg15.18-ts2.14.2"
    assert kwargs["build_args"] == {"PG_VERSION": "15.18", "TS_VERSION": "2.14.2"}


def test_new_checks_compatibility_by_postgres_major():
    state = MagicMock()
    state.engine.value = "docker"
    state.version_manager.is_compatible.return_value = True
    state.docker_client.create_container.return_value = "container-123"
    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.new,
            ["--postgres", "15.18", "--timescaledb", "2.14.2", "--port", "55432"],
        )

    assert result.exit_code == 0, result.output
    state.version_manager.is_compatible.assert_called_once_with("15", "2.14.2")


def test_patch_release_uses_published_ha_base():
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {"name": "pg15.18-ts2.28.2"},
            {"name": "pg15.18-ts2.28.3-all"},
            {"name": "pg15.18-ts2.28.3"},
        ]
    }
    with patch("tsdbenv.docker_utils.requests.get", return_value=response):
        image = DockerClient._timescale_base_image("15.18")

    assert image == "timescale/timescaledb-ha:pg15.18-ts2.28.3"
