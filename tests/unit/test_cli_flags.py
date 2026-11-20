from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tsdbenv import cli
from tsdbenv.engine_config import Engine
from tsdbenv.models import Container


def _state():
    state = MagicMock()
    state.engine.value = "docker"
    state.verbose = False
    state.version_manager.is_compatible.return_value = True
    state.docker_client.create_container.return_value = "container-123"
    return state


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("option", ["--version", "-v"])
def test_root_version_flags(option, repeat):
    result = CliRunner().invoke(cli.main, [option])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"tsdbenv {cli.__version__}"


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize(
    ("engine_option", "engine"), [("--engine", "podman"), ("-e", "docker")]
)
def test_root_engine_flags(engine_option, engine, repeat):
    state = _state()
    state.state_tracker.load_containers.return_value = []

    with (
        patch.object(cli, "cli_state", state),
        patch.object(cli, "init_cli_state") as init_state,
    ):
        result = CliRunner().invoke(
            cli.main, [engine_option, engine, "--verbose", "list"]
        )

    assert result.exit_code == 0, result.output
    assert "No containers found." in result.output
    init_state.assert_called_once_with(Engine(engine), verbose=True)


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize(
    ("init_option", "tablespaces_option"),
    [
        ("--init", "--tablespaces"),
        ("--init", "-t"),
        ("-i", "--tablespaces"),
        ("-i", "-t"),
    ],
)
def test_new_accepts_and_applies_every_option(
    init_option, tablespaces_option, repeat, tmp_path
):
    config_file = tmp_path / "postgresql.conf"
    config_file.write_text("work_mem = 77MB\n", encoding="utf-8")
    init_file = tmp_path / "init.sql"
    init_file.write_text("SELECT 1;\n", encoding="utf-8")
    state = _state()
    state.docker_client.create_tablespaces.return_value = {
        "fast": True,
        "archive": True,
    }

    args = [
        "--postgres",
        "16",
        "--timescaledb",
        "2.22.1",
        "--port",
        "55432",
        "--config",
        str(config_file),
        "--name",
        "flags-db",
        "--bind-ip",
        "127.0.0.1",
        init_option,
        str(init_file),
        tablespaces_option,
        "fast,archive",
        "--force",
        "--rebuild",
        "--verbose",
    ]

    with (
        patch.object(cli, "cli_state", state),
        patch.object(cli.NetworkValidator, "validate_bind_ip", return_value=(True, "")),
    ):
        result = CliRunner().invoke(cli.new, args)

    assert result.exit_code == 0, result.output
    state.version_manager.get_or_fetch.assert_called_once()
    state.version_manager.is_compatible.assert_not_called()
    image_kwargs = state.docker_client.prepare_image.call_args.kwargs
    assert image_kwargs["rebuild"] is True
    create_kwargs = state.docker_client.create_container.call_args.kwargs
    assert create_kwargs["image"] == "tsdbenv:pg16-ts2.22.1-v4"
    assert create_kwargs["name"] == "flags-db"
    assert create_kwargs["ports"] == {5432: 55432}
    assert create_kwargs["bind_ip"] == "127.0.0.1"
    assert create_kwargs["command"] == ["postgres", "-c", "work_mem=77MB"]
    state.docker_client.wait_for_postgres.assert_called_once_with(
        "container-123", timeout=60, require_extensions=True
    )
    state.docker_client.execute_sql_file.assert_called_once_with(
        "container-123", str(init_file)
    )
    state.docker_client.create_tablespaces.assert_called_once_with(
        "container-123", ["fast", "archive"]
    )


@pytest.mark.parametrize("repeat", range(3))
def test_removeall_force_skips_confirmation(repeat):
    state = _state()
    container = Container(
        name="db-one",
        postgres_version="16",
        timescaledb_version="2.22.1",
        created_at=cli.datetime.now(),
        last_accessed_at=cli.datetime.now(),
        docker_id="container-123",
        tsdbadmin_password="secret",
    )
    state.state_tracker.load_containers.return_value = [container]

    with (
        patch.object(cli, "cli_state", state),
        patch.object(cli.click, "confirm") as confirm,
    ):
        result = CliRunner().invoke(cli.removeall, ["--force"])

    assert result.exit_code == 0, result.output
    assert "Removed 1/1 container(s)" in result.output
    confirm.assert_not_called()
    state.docker_client.remove_container.assert_called_once_with("container-123")
    state.state_tracker.delete_container.assert_called_once_with("db-one")


@pytest.mark.parametrize("repeat", range(3))
def test_tablespaces_names_option(repeat):
    state = _state()
    container = Container(
        name="db-one",
        postgres_version="16",
        timescaledb_version="2.22.1",
        created_at=cli.datetime.now(),
        last_accessed_at=cli.datetime.now(),
        docker_id="container-123",
        tsdbadmin_password="secret",
    )
    state.state_tracker.load_containers.return_value = [container]
    state.docker_client.create_tablespaces.return_value = {"fast": True}

    with patch.object(cli, "cli_state", state):
        result = CliRunner().invoke(
            cli.create_tablespaces, ["db-one", "--names", "fast"]
        )

    assert result.exit_code == 0, result.output
    state.docker_client.create_tablespaces.assert_called_once_with(
        "container-123", ["fast"]
    )


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize(
    ("alias", "command"),
    [
        ("-n", "new"),
        ("-l", "list"),
        ("-r", "remove"),
        ("-c", "connectstring"),
        ("-g", "versionrefresh"),
        ("-m", "matrix"),
        ("-a", "removeall"),
        ("-t", "tablespaces"),
    ],
)
def test_command_aliases(alias, command, repeat, monkeypatch):
    argv = ["tsdbenv", alias]
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli._expand_short_aliases()

    assert argv == ["tsdbenv", command]


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize(
    "command_name",
    [
        "new",
        "list",
        "logs",
        "remove",
        "removeall",
        "connectstring",
        "tablespaces",
        "versionrefresh",
        "matrix",
    ],
)
def test_each_command_accepts_help(command_name, repeat):
    with patch.object(cli, "init_cli_state"):
        result = CliRunner().invoke(cli.main, [command_name, "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
