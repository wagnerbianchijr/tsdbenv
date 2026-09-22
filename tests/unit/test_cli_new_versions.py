from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tsdbenv import cli
from tsdbenv.docker_utils import DockerClient
from tsdbenv.models import Container


def test_spinner_formats_elapsed_time():
    assert cli.Spinner._format_elapsed(0) == "00:00"
    assert cli.Spinner._format_elapsed(65.9) == "01:05"
    assert cli.Spinner._format_elapsed(3661) == "01:01:01"


def test_connection_info_shows_cloud_and_on_premises_commands(capsys):
    container = Container(
        name="tsdb-c4518ff8",
        postgres_version="15.18",
        timescaledb_version="2.14.2",
        created_at=cli.datetime.now(),
        last_accessed_at=cli.datetime.now(),
        docker_id="container-123",
        port=5433,
        bind_ip="127.0.0.1",
        tsdbadmin_password="cL6SLghbZVstIgdG",
    )

    cli.display_connection_info(container)

    output = capsys.readouterr().out
    assert "Container 'tsdb-c4518ff8' created successfully!" in output
    assert (
        'psql "postgresql://tsdbadmin:cL6SLghbZVstIgdG@127.0.0.1:5433/tsdb"'
        "  -- tiger cloud environment"
    ) in output
    assert (
        'psql "postgresql://postgres:postgres@127.0.0.1:5433/tsdb"'
        "           -- on-premises environment"
    ) in output


def test_connectstring_shows_cloud_and_on_premises_commands():
    container = Container(
        name="tsdb-c4518ff8",
        postgres_version="15.18",
        timescaledb_version="2.14.2",
        created_at=cli.datetime.now(),
        last_accessed_at=cli.datetime.now(),
        docker_id="container-123",
        port=5433,
        bind_ip="127.0.0.1",
        tsdbadmin_password="cL6SLghbZVstIgdG",
    )
    state = MagicMock()
    state.state_tracker.load_containers.return_value = [container]

    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(cli.connectstring, [container.name])

    assert result.exit_code == 0, result.output
    assert "-- tiger cloud environment" in result.output
    assert 'psql "postgresql://postgres:postgres@127.0.0.1:5433/tsdb"' in result.output
    assert "-- on-premises environment" in result.output
    state.state_tracker.mark_accessed.assert_called_once_with(container.name)


def test_new_uses_exact_postgres_and_timescaledb_releases():
    state = MagicMock()
    state.engine.value = "docker"
    state.verbose = False
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
    assert kwargs["tag"] == "tsdbenv:pg15.18-ts2.14.2-v4"
    assert kwargs["build_args"] == {"PG_VERSION": "15.18", "TS_VERSION": "2.14.2"}
    assert kwargs["pull"] is False
    assert "Preparing PostgreSQL 15.18 + TimescaleDB 2.14.2 image" in result.output
    assert "Creating container tsdb-" in result.output
    assert "[00:00]" in result.output
    environment = state.docker_client.create_container.call_args.kwargs["environment"]
    assert environment == {
        "POSTGRES_PASSWORD": "postgres",
        "POSTGRESQL_PASSWORD": "postgres",
        "PGPASSWORD": "postgres",
    }


def test_new_checks_compatibility_by_postgres_major():
    state = MagicMock()
    state.engine.value = "docker"
    state.verbose = False
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
