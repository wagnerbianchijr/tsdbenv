# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

import os
from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from tsdbenv.docker_utils import DockerClient
from tsdbenv.engine_config import Engine, get_socket_path


@pytest.fixture
def mock_docker_client():
    """Patch docker.from_env to return a MagicMock client (for Docker engine)."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client
        yield fake_client


def test_init_success(mock_docker_client):
    """DockerClient initializes when the daemon is reachable."""
    client = DockerClient()
    assert client.client is mock_docker_client
    mock_docker_client.ping.assert_called_once()


def test_init_with_docker_engine(mock_docker_client):
    """DockerClient initializes with explicit docker engine."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient(engine="docker")

        assert client.client is fake_client
        mock_from_env.assert_called_once()
        fake_client.ping.assert_called_once()


def test_init_with_podman_engine(mock_docker_client):
    """DockerClient initializes with explicit podman engine."""
    import os

    with (
        patch("tsdbenv.docker_utils.docker.DockerClient") as mock_docker_client_ctor,
        patch("tsdbenv.docker_utils.Path.exists", return_value=False),
        patch.dict(os.environ, {"DOCKER_HOST": ""}, clear=False),
    ):
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_docker_client_ctor.return_value = fake_client

        client = DockerClient(engine="podman")

        assert client.client is fake_client
        socket_path = get_socket_path(Engine.PODMAN)
        mock_docker_client_ctor.assert_called_once_with(
            base_url=f"unix://{socket_path}"
        )
        fake_client.ping.assert_called_once()


def test_init_raises_when_docker_not_running():
    """DockerClient raises RuntimeError when ping fails."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.side_effect = Exception("connection refused")
        mock_from_env.return_value = fake_client
        with pytest.raises(
            RuntimeError, match="Docker is not running or not accessible"
        ):
            DockerClient()


def test_init_raises_when_podman_not_running():
    """DockerClient raises RuntimeError with podman install message when podman not running."""
    with patch("tsdbenv.docker_utils.docker.DockerClient") as mock_docker_client:
        fake_client = MagicMock()
        fake_client.ping.side_effect = Exception("connection refused")
        mock_docker_client.return_value = fake_client
        with pytest.raises(
            RuntimeError, match="Podman is not running or not accessible"
        ):
            DockerClient(engine="podman")


def test_check_docker_installed_true():
    """Test check_docker_installed returns True when ping succeeds."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        assert client.check_docker_installed() is True


def test_check_docker_installed_false():
    """Test check_docker_installed returns False when ping fails."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        # First ping succeeds for __init__, second fails for check_docker_installed
        fake_client.ping.side_effect = [True, Exception("boom")]
        mock_from_env.return_value = fake_client

        client = DockerClient()
        assert client.check_docker_installed() is False


def test_create_container_success():
    """Test successful container creation."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_container.id = "abc123"
        fake_client.containers.run.return_value = fake_container

        with patch.object(client, "wait_for_postgres", return_value=True) as mock_wait:
            container_id = client.create_container(
                image="postgres:14-alpine",
                name="testdb",
                environment={"POSTGRES_PASSWORD": "postgres"},
                ports={5432: 5432},
            )

        assert container_id == "abc123"
        mock_wait.assert_called_once_with("abc123")
        fake_client.containers.run.assert_called_once()
        _, kwargs = fake_client.containers.run.call_args
        assert kwargs["name"] == "testdb"
        assert kwargs["detach"] is True
        assert kwargs["remove"] is False
        assert kwargs["restart_policy"] == {"Name": "unless-stopped"}


def test_create_container_port_conflict():
    """Test port conflict error handling."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_client.containers.run.side_effect = docker.errors.APIError(
            "Address already in use"
        )

        with pytest.raises(docker.errors.APIError, match="Port already in use"):
            client.create_container(
                image="postgres:14-alpine",
                name="testdb",
                environment={},
                ports={5432: 5432},
            )


def test_create_container_other_api_error_propagates():
    """Test other API errors propagate correctly."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_client.containers.run.side_effect = docker.errors.APIError(
            "some other error"
        )

        with pytest.raises(docker.errors.APIError, match="some other error"):
            client.create_container(
                image="postgres:14-alpine",
                name="testdb",
                environment={},
                ports={5432: 5432},
            )


def test_image_exists_for_local_tag(mock_docker_client):
    """Test local image lookup succeeds without a registry request."""
    client = DockerClient()

    assert client.image_exists("example/image:pg15") is True
    mock_docker_client.images.get.assert_called_once_with("example/image:pg15")


def test_image_exists_returns_false_when_missing(mock_docker_client):
    """Test missing local image is reported without raising."""
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("missing")
    client = DockerClient()

    assert client.image_exists("example/image:pg15") is False


def test_prepare_image_reuses_local_image(mock_docker_client):
    """Test cached images avoid pull and build work."""
    image = MagicMock(id="image-123")
    mock_docker_client.images.get.return_value = image
    client = DockerClient()

    result = client.prepare_image(
        tag="example/image:pg15",
        dockerfile_dir="/tmp/dockerfiles",
        build_args={"PG_VERSION": "15"},
    )

    assert result == "image-123"
    mock_docker_client.images.pull.assert_not_called()


def test_prepare_image_pulls_on_cache_miss(mock_docker_client):
    """Test a prebuilt registry image is preferred over a local build."""
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("missing")
    mock_docker_client.images.pull.return_value = MagicMock(id="pulled-123")
    client = DockerClient()

    with patch.object(client, "build_image") as build_image:
        result = client.prepare_image(
            tag="example/image:pg15",
            dockerfile_dir="/tmp/dockerfiles",
        )

    assert result == "pulled-123"
    build_image.assert_not_called()


def test_prepare_image_builds_when_pull_fails(mock_docker_client):
    """Test registry failures fall back to a local build."""
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("missing")
    mock_docker_client.images.pull.side_effect = docker.errors.APIError("unavailable")
    client = DockerClient()

    with patch.object(client, "build_image", return_value="built-123") as build_image:
        result = client.prepare_image(
            tag="example/image:pg15",
            dockerfile_dir="/tmp/dockerfiles",
            build_args={"PG_VERSION": "15"},
        )

    assert result == "built-123"
    build_image.assert_called_once()


def test_prepare_image_can_skip_registry_pull(mock_docker_client):
    """Test pair-specific local images build without a failed registry lookup."""
    mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound("missing")
    client = DockerClient()

    with patch.object(client, "build_image", return_value="built-123") as build_image:
        result = client.prepare_image(
            tag="tsdbenv:pg15.18-ts2.14.2-v2",
            dockerfile_dir="/tmp/dockerfiles",
            pull=False,
        )

    assert result == "built-123"
    mock_docker_client.images.pull.assert_not_called()
    build_image.assert_called_once()


def test_prepare_image_rebuilds_when_requested(mock_docker_client):
    """Test --rebuild bypasses both local image reuse and registry pulls."""
    client = DockerClient()

    with patch.object(client, "build_image", return_value="built-123") as build_image:
        result = client.prepare_image(
            tag="example/image:pg15",
            dockerfile_dir="/tmp/dockerfiles",
            rebuild=True,
        )

    assert result == "built-123"
    mock_docker_client.images.get.assert_not_called()
    mock_docker_client.images.pull.assert_not_called()
    build_image.assert_called_once()


def test_start_container():
    """Test starting a container."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_client.containers.get.return_value = fake_container

        client.start_container("abc123")

        fake_client.containers.get.assert_called_once_with("abc123")
        fake_container.start.assert_called_once()


def test_stop_container():
    """Test stopping a container."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_client.containers.get.return_value = fake_container

        client.stop_container("abc123")

        fake_container.stop.assert_called_once_with(timeout=10)


def test_remove_container_running():
    """Test removing a running container."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_container.status = "running"
        fake_client.containers.get.return_value = fake_container

        client.remove_container("abc123")

        fake_container.stop.assert_called_once_with(timeout=10)
        fake_container.remove.assert_called_once_with(force=True)


def test_remove_container_already_stopped():
    """Test removing a stopped container."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_container.status = "exited"
        fake_client.containers.get.return_value = fake_container

        client.remove_container("abc123")

        fake_container.stop.assert_not_called()
        fake_container.remove.assert_called_once_with(force=True)


def test_remove_container_not_found():
    """Test removing a container that no longer exists in Docker."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_client.containers.get.side_effect = docker.errors.NotFound(
            "Container not found"
        )

        # Should not raise an exception
        client.remove_container("nonexistent")

        fake_client.containers.get.assert_called_once_with("nonexistent")


def test_get_container_logs():
    """Test getting container logs."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_container.logs.return_value = (
            b"database system is ready to accept connections\n"
        )
        fake_client.containers.get.return_value = fake_container

        logs = client.get_container_logs("abc123")

        assert "database system is ready to accept connections" in logs
        fake_container.logs.assert_called_once_with(stdout=True, stderr=True)


def test_list_containers():
    """Test listing containers."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock()
        fake_container.id = "abc123"
        fake_container.name = "testdb"
        fake_container.status = "running"
        fake_container.ports = {"5432/tcp": [{"HostPort": "5432"}]}
        fake_client.containers.list.return_value = [fake_container]

        result = client.list_containers()

        assert result == [
            {
                "id": "abc123",
                "name": "testdb",
                "status": "running",
                "ports": {"5432/tcp": [{"HostPort": "5432"}]},
            }
        ]
        fake_client.containers.list.assert_called_once_with(all=True)


def test_wait_for_postgres_ready_immediately():
    """Test readiness requires the initialized extension set."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock(status="running")
        fake_container.exec_run.return_value = MagicMock(exit_code=0, output=b"6\n")
        fake_client.containers.get.return_value = fake_container

        assert client.wait_for_postgres("abc123", timeout=5) is True
        fake_container.exec_run.assert_called_once()


def test_wait_for_postgres_timeout():
    """Test readiness times out while extensions are incomplete."""
    with patch("tsdbenv.docker_utils.docker.from_env") as mock_from_env:
        fake_client = MagicMock()
        fake_client.ping.return_value = True
        mock_from_env.return_value = fake_client

        client = DockerClient()
        fake_container = MagicMock(status="running")
        fake_container.exec_run.return_value = MagicMock(exit_code=0, output=b"5\n")
        fake_client.containers.get.return_value = fake_container

        with (
            patch("tsdbenv.docker_utils.time.monotonic", side_effect=[0, 0, 2]),
            patch("tsdbenv.docker_utils.time.sleep"),
        ):
            with pytest.raises(TimeoutError, match="required extensions not ready"):
                client.wait_for_postgres("abc123", timeout=1)


def test_wait_for_postgres_fails_when_container_exits(mock_docker_client):
    """Test startup failures surface container logs immediately."""
    client = DockerClient()
    fake_container = MagicMock(status="exited")
    fake_container.logs.return_value = b"initialization failed"
    mock_docker_client.containers.get.return_value = fake_container

    with pytest.raises(RuntimeError, match="initialization failed"):
        client.wait_for_postgres("abc123", timeout=5)
