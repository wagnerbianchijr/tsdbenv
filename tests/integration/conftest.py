# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clean_state():
    """Clean state before and after each test."""
    state_file = Path.home() / ".tsdbenv" / "containers.json"
    if state_file.exists():
        state_file.unlink()
    yield
    if state_file.exists():
        state_file.unlink()


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for integration tests."""
    with patch("docker.from_env") as mock:
        yield mock


@pytest.fixture
def mock_docker_container():
    """Mock Docker container object."""
    mock_container = MagicMock()
    mock_container.id = "abc123def456"
    mock_container.status = "running"
    mock_container.logs.return_value = b"PostgreSQL started\n"
    return mock_container


@pytest.fixture
def mock_cli_state():
    """Mock CLI state with isolated Docker and state tracker."""
    import tsdbenv.cli

    with patch.object(
        tsdbenv.cli.cli_state, "docker_client"
    ) as mock_docker, patch.object(
        tsdbenv.cli.cli_state, "state_tracker"
    ) as mock_tracker, patch.object(
        tsdbenv.cli.cli_state, "version_manager"
    ) as mock_vm:
        mock_docker.build_image = MagicMock(return_value="image-123")
        mock_docker.prepare_image = MagicMock(return_value="image-123")
        mock_docker.create_container = MagicMock(return_value="container-123")
        mock_docker.remove_container = MagicMock()
        mock_docker.get_container_logs = MagicMock(return_value="logs")
        mock_docker.wait_for_postgres = MagicMock()
        mock_docker.execute_sql_file = MagicMock()
        mock_docker.create_tablespaces = MagicMock(return_value={})

        mock_tracker.load_containers = MagicMock(return_value=[])
        mock_tracker.save_container = MagicMock()
        mock_tracker.delete_container = MagicMock()
        mock_tracker.mark_accessed = MagicMock()
        mock_tracker.get_stale_containers = MagicMock(return_value=[])

        mock_vm.refresh = MagicMock()
        mock_vm.get_or_fetch = MagicMock()
        mock_vm.is_compatible = MagicMock(return_value=True)

        yield {"docker": mock_docker, "tracker": mock_tracker, "vm": mock_vm}
