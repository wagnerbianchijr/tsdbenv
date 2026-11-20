from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tsdbenv import cli
from tsdbenv.models import Container


def _cli_state():
    state = MagicMock()
    state.engine.value = "docker"
    state.verbose = False
    state.version_manager.is_compatible.return_value = True
    state.docker_client.create_container.return_value = "container-123"
    return state


@pytest.mark.parametrize("repeat", range(3))
def test_postgres_only_container_skips_timescale_setup(repeat):
    state = _cli_state()

    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.new,
            [
                "--postgres",
                "16",
                "--name",
                "pg-only",
                "--bind-ip",
                "127.0.0.1",
                "--port",
                "55432",
            ],
        )

    assert result.exit_code == 0, result.output
    state.version_manager.get_or_fetch.assert_not_called()
    state.docker_client.prepare_image.assert_not_called()
    kwargs = state.docker_client.create_container.call_args.kwargs
    assert kwargs["image"] == "postgres:16"
    assert kwargs["name"] == "pg-only"
    assert kwargs["require_extensions"] is False
    assert kwargs["environment"]["POSTGRES_DB"] == "tsdb"
    assert "tsdbadmin" not in result.output


@pytest.mark.parametrize("repeat", range(3))
def test_custom_name_is_passed_to_container_creation(repeat):
    state = _cli_state()

    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.new,
            [
                "--postgres",
                "16",
                "--timescaledb",
                "2.22.1",
                "--force",
                "--name",
                "named-db",
                "--bind-ip",
                "127.0.0.1",
                "--port",
                "55432",
            ],
        )

    assert result.exit_code == 0, result.output
    assert state.docker_client.create_container.call_args.kwargs["name"] == "named-db"


@pytest.mark.parametrize("repeat", range(3))
def test_non_tty_progress_is_plain_and_bounded(repeat):
    state = _cli_state()

    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.new,
            [
                "--postgres",
                "16",
                "--timescaledb",
                "2.22.1",
                "--force",
                "--port",
                "55432",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "\r" not in result.output
    assert result.output.count("Loading TimescaleDB compatibility data...") == 1
    assert (
        result.output.count("Preparing PostgreSQL 16 + TimescaleDB 2.22.1 image...")
        == 1
    )
    assert result.output.count("Creating container tsdb-") == 1
    assert result.output.count("Done") == 3


@pytest.mark.parametrize("repeat", range(3))
def test_displayed_connection_strings_never_contain_generated_password(repeat, capsys):
    secret = "generated-secret-that-must-not-appear"
    container = Container(
        name="tsdb-test",
        postgres_version="16",
        timescaledb_version="2.22.1",
        created_at=cli.datetime.now(),
        last_accessed_at=cli.datetime.now(),
        docker_id="container-123",
        port=55432,
        bind_ip="127.0.0.1",
        tsdbadmin_password=secret,
    )
    state = _cli_state()
    state.state_tracker.load_containers.return_value = [container]

    cli.display_connection_info(container)
    created_output = capsys.readouterr().out
    with patch.object(cli, "cli_state", state):
        connection_output = CliRunner().invoke(cli.connectstring, [container.name])

    assert secret not in created_output
    assert secret not in connection_output.output
    assert "postgresql://tsdbadmin@127.0.0.1:55432/tsdb" in created_output
    assert "password is stored in the local tsdbenv registry" in created_output


@pytest.mark.parametrize("repeat", range(3))
def test_config_values_are_passed_as_postgres_startup_options(repeat, tmp_path):
    config_file = tmp_path / "postgresql.conf"
    config_file.write_text(
        "work_mem = 77MB\n"
        "track_io_timing = on\n"
        "shared_preload_libraries = 'timescaledb,pg_stat_statements'\n",
        encoding="utf-8",
    )
    state = _cli_state()

    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.new,
            [
                "--postgres",
                "16",
                "--timescaledb",
                "2.22.1",
                "--force",
                "--config",
                str(config_file),
                "--bind-ip",
                "127.0.0.1",
                "--port",
                "55432",
            ],
        )

    assert result.exit_code == 0, result.output
    assert state.docker_client.create_container.call_args.kwargs["command"] == [
        "postgres",
        "-c",
        "work_mem=77MB",
        "-c",
        "track_io_timing=on",
        "-c",
        "shared_preload_libraries=timescaledb,pg_stat_statements",
    ]
