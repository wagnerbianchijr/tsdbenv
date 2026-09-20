# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

"""Real Docker integration tests using actual Docker containers.

These tests verify the complete Docker lifecycle with real containers.
They require Docker to be running and will create/destroy test containers.

Skip gracefully if Docker is unavailable.
"""

import time
import uuid
from pathlib import Path
from typing import Generator

import docker
import docker.errors
import psycopg
import pytest

from tsdbenv.docker_utils import DockerClient


def _is_docker_available() -> bool:
    """Check if Docker is available for integration tests."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def cleanup_containers():
    """Generator that tracks containers to clean up after tests."""
    containers_to_cleanup = []

    def _register_container(container_id: str) -> None:
        containers_to_cleanup.append(container_id)

    yield _register_container

    # Cleanup: remove all registered containers
    if containers_to_cleanup:
        try:
            client = docker.from_env()
            for cid in containers_to_cleanup:
                try:
                    container = client.containers.get(cid)
                    if container.status in ["running", "paused"]:
                        container.stop(timeout=5)
                    container.remove(force=True)
                except docker.errors.NotFound:
                    pass  # Already removed
                except Exception:
                    pass  # Ignore cleanup errors
        except Exception:
            pass  # Docker not available


@pytest.mark.skipif(
    not _is_docker_available(),
    reason="Docker not available",
)
class TestDockerRealLifecycle:
    """Real Docker integration tests."""

    def test_full_container_lifecycle(self, cleanup_containers):
        """Test full container lifecycle: create → list → logs → stop → remove.

        This is an end-to-end test with a real container.
        """

        client = DockerClient()
        container_name = f"tsdbenv-test-{uuid.uuid4().hex[:8]}"

        try:
            # Create container directly (skip wait_for_postgres)
            # Use sleep to keep container running
            raw_container = client.client.containers.run(
                "alpine:latest",
                "sleep 3600",
                name=container_name,
                environment={"TEST": "value"},
                detach=True,
                remove=False,
            )
            container_id = raw_container.id
            cleanup_containers(container_id)
            assert container_id is not None
            assert len(container_id) > 0

            # List containers (should include our new one)
            containers = client.list_containers()
            container_names = [c["name"] for c in containers]
            assert container_name in container_names

            # Find our container in the list
            our_container = next(c for c in containers if c["name"] == container_name)
            assert our_container["status"] == "running"
            assert our_container["id"] == container_id

            # Get logs
            logs = client.get_container_logs(container_id)
            assert isinstance(logs, str)

            # Stop container
            client.stop_container(container_id)
            containers = client.list_containers()
            stopped_container = next(c for c in containers if c["id"] == container_id)
            assert stopped_container["status"] == "exited"

            # Restart container
            client.start_container(container_id)
            containers = client.list_containers()
            restarted_container = next(c for c in containers if c["id"] == container_id)
            assert restarted_container["status"] == "running"

            # Remove container
            client.remove_container(container_id)
            containers = client.list_containers()
            container_ids = [c["id"] for c in containers]
            assert container_id not in container_ids

        except docker.errors.NotFound as e:
            pytest.fail(f"Docker container not found: {e}")

    def test_multiple_containers(self, cleanup_containers):
        """Test creating, listing, and removing multiple containers.

        This verifies the system handles multiple containers correctly.
        """

        client = DockerClient()
        container_ids = []

        try:
            # Create 3 containers directly (skip wait_for_postgres)
            for i in range(3):
                container_name = f"tsdbenv-multi-{uuid.uuid4().hex[:8]}"
                raw_container = client.client.containers.run(
                    "alpine:latest",
                    "sleep 3600",
                    name=container_name,
                    detach=True,
                    remove=False,
                )
                container_id = raw_container.id
                container_ids.append(container_id)
                cleanup_containers(container_id)

            # List and verify all 3 are present
            containers = client.list_containers()
            listed_ids = [c["id"] for c in containers]
            for cid in container_ids:
                assert cid in listed_ids

            # Stop one container
            client.stop_container(container_ids[0])
            containers = client.list_containers()
            stopped = next(c for c in containers if c["id"] == container_ids[0])
            assert stopped["status"] == "exited"

            # Remove one container
            client.remove_container(container_ids[0])
            containers = client.list_containers()
            listed_ids = [c["id"] for c in containers]
            assert container_ids[0] not in listed_ids

            # Verify the other 2 still exist
            for cid in container_ids[1:]:
                assert cid in listed_ids

            # Remove remaining containers
            for cid in container_ids[1:]:
                client.remove_container(cid)

            # Verify all are gone
            containers = client.list_containers()
            listed_ids = [c["id"] for c in containers]
            for cid in container_ids:
                assert cid not in listed_ids

        except docker.errors.NotFound as e:
            pytest.fail(f"Docker container not found during multi-container test: {e}")

    def test_start_stop_not_found(self):
        """Test error handling when container doesn't exist."""

        client = DockerClient()
        fake_id = "nonexistent_container_xyz123"

        with pytest.raises(docker.errors.NotFound):
            client.start_container(fake_id)

        with pytest.raises(docker.errors.NotFound):
            client.stop_container(fake_id)

        # remove_container gracefully handles NotFound errors
        client.remove_container(fake_id)

    def test_get_logs_not_found(self):
        """Test error handling when getting logs from non-existent container."""

        client = DockerClient()
        fake_id = "nonexistent_container_xyz123"

        with pytest.raises(docker.errors.NotFound):
            client.get_container_logs(fake_id)


@pytest.mark.skipif(
    not _is_docker_available(),
    reason="Docker not available",
)
class TestRealTsdbenvImage:
    """Integration tests with actual tsdbenv Docker image."""

    @pytest.fixture
    def built_image(self, cleanup_containers):
        """Build the tsdbenv image for testing."""
        client = DockerClient()
        dockerfile_dir = Path(__file__).parent.parent.parent / "src/tsdbenv/dockerfiles"

        if not dockerfile_dir.exists():
            pytest.skip(f"Dockerfile directory not found: {dockerfile_dir}")

        image_tag = f"tsdbenv:test-pg14-{uuid.uuid4().hex[:8]}"

        try:
            # Build the image
            client.build_image(
                dockerfile_dir=str(dockerfile_dir),
                tag=image_tag,
                build_args={"PG_VERSION": "14"},
            )
            yield image_tag
        finally:
            # Cleanup built image
            try:
                client.client.images.remove(image_tag, force=True)
            except Exception:
                pass  # Ignore cleanup errors

    def test_real_tsdbenv_image_builds(self, built_image):
        """Test that the tsdbenv image builds successfully."""
        client = DockerClient()
        images = client.client.images.list()
        image_tags = []
        for image in images:
            image_tags.extend(image.tags)

        assert built_image in image_tags

    def test_tsdbenv_container_creation_and_postgres_ready(
        self, built_image, cleanup_containers
    ):
        """Build and create container, verify PostgreSQL is ready.

        This test:
        1. Creates a container from tsdbenv image
        2. Waits for PostgreSQL to be ready
        3. Verifies logs contain expected initialization messages
        """
        client = DockerClient()
        container_name = f"tsdbenv-pg14-{uuid.uuid4().hex[:8]}"
        password = f"test_pwd_{uuid.uuid4().hex[:8]}"

        try:
            # Create and start container (use random port to avoid conflicts)
            container_id = client.create_container(
                image=built_image,
                name=container_name,
                environment={"POSTGRES_PASSWORD": "postgres"},
                ports={5432: None},
                tsdbadmin_password=password,
            )
            cleanup_containers(container_id)
            assert container_id is not None
            assert len(container_id) > 0

            # Verify PostgreSQL is ready (create_container calls wait_for_postgres)
            logs = client.get_container_logs(container_id)
            assert "database system is ready to accept connections" in logs

        except TimeoutError:
            pytest.fail("PostgreSQL failed to start within timeout")

    def test_tsdbadmin_user_created_in_container(self, built_image, cleanup_containers):
        """Test that tsdbadmin user is created with correct password.

        This test:
        1. Creates container with tsdbenv image
        2. Waits for PostgreSQL ready
        3. Connects as tsdbadmin with the provided password
        4. Verifies the role attributes match Tiger Cloud
        """
        client = DockerClient()
        container_name = f"tsdbenv-admin-{uuid.uuid4().hex[:8]}"
        password = "test_tsdbadmin_password_123"

        try:
            # Create container with tsdbadmin password
            container_id = client.create_container(
                image=built_image,
                name=container_name,
                environment={"POSTGRES_PASSWORD": "postgres"},
                ports={5432: None},  # Let Docker assign random port
                tsdbadmin_password=password,
            )
            cleanup_containers(container_id)

            # Get container to retrieve assigned port
            container = client.client.containers.get(container_id)
            ports_info = container.ports
            if not ports_info or "5432/tcp" not in ports_info:
                pytest.fail("Could not determine PostgreSQL port")

            port_mapping = ports_info["5432/tcp"]
            if not port_mapping:
                pytest.fail("No port mapping found")

            assigned_port = port_mapping[0]["HostPort"]
            host_port = int(assigned_port)

            # Wait a bit for container to fully initialize
            time.sleep(2)

            # Try to connect as tsdbadmin
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    with psycopg.connect(
                        host="localhost",
                        port=host_port,
                        user="tsdbadmin",
                        password=password,
                        dbname="postgres",
                    ) as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT rolsuper, rolcreaterole, rolreplication
                                FROM pg_roles
                                WHERE rolname = current_user
                                """
                            )
                            result = cur.fetchone()
                            assert result is not None
                            assert result == (False, True, True)
                    break
                except psycopg.OperationalError as e:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        pytest.fail(
                            f"Failed to connect as tsdbadmin after {max_retries} attempts: {e}"
                        )

        except TimeoutError:
            pytest.fail("PostgreSQL failed to start within timeout")

    def test_timescaledb_extensions_available(self, built_image, cleanup_containers):
        """Test that TimescaleDB and Toolkit are available in the container.

        This test:
        1. Creates container from tsdbenv image
        2. Connects as postgres user
        3. Verifies TimescaleDB extension is in shared_preload_libraries
        4. Verifies TimescaleDB and Toolkit are loaded in the tsdb database
        """
        client = DockerClient()
        container_name = f"tsdbenv-ext-{uuid.uuid4().hex[:8]}"

        try:
            container_id = client.create_container(
                image=built_image,
                name=container_name,
                environment={"POSTGRES_PASSWORD": "postgres"},
                ports={5432: None},
                tsdbadmin_password="test_password",
            )
            cleanup_containers(container_id)

            # Get assigned port
            container = client.client.containers.get(container_id)
            ports_info = container.ports
            if not ports_info or "5432/tcp" not in ports_info:
                pytest.fail("Could not determine PostgreSQL port")

            port_mapping = ports_info["5432/tcp"]
            assigned_port = int(port_mapping[0]["HostPort"])

            # Wait for container initialization
            time.sleep(2)

            # Connect and verify extension
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    with psycopg.connect(
                        host="localhost",
                        port=assigned_port,
                        user="postgres",
                        password="postgres",
                        dbname="tsdb",
                    ) as conn:
                        with conn.cursor() as cur:
                            # Check shared_preload_libraries
                            cur.execute("SHOW shared_preload_libraries")
                            preload = cur.fetchone()[0]
                            assert "timescaledb" in preload

                            # Verify core TimescaleDB and Toolkit are installed.
                            cur.execute(
                                """
                                SELECT extname, extversion
                                FROM pg_extension
                                WHERE extname IN ('timescaledb', 'timescaledb_toolkit')
                                """
                            )
                            extensions = dict(cur.fetchall())
                            assert set(extensions) == {
                                "timescaledb",
                                "timescaledb_toolkit",
                            }
                            assert all(
                                "." in version for version in extensions.values()
                            )
                    break
                except psycopg.OperationalError as e:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        pytest.fail(f"Failed to verify TimescaleDB extension: {e}")

        except TimeoutError:
            pytest.fail("PostgreSQL failed to start within timeout")
