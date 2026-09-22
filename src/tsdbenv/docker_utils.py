# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import docker
import docker.errors
import requests

from tsdbenv.engine_config import Engine, get_engine_from_cli_or_env, get_socket_path


class DockerClient:
    """Wrapper around Docker SDK for container lifecycle management."""

    REQUIRED_EXTENSIONS = (
        "timescaledb",
        "postgres_fdw",
        "pg_buffercache",
        "pg_stat_statements",
        "timescaledb_toolkit",
        "vector",
    )

    def __init__(self, engine: Optional[str] = None) -> None:
        """Initialize Docker client with engine-specific socket.

        This wrapper automatically detects and connects to the correct container engine
        socket based on the provided engine parameter, environment variable (TSDBENV_ENGINE),
        or default (Docker). The socket path is determined by engine_config.get_socket_path(),
        which returns /var/run/docker.sock for Docker or /run/user/{uid}/podman/podman.sock
        for rootless Podman.

        For rootless Podman, port binding uses slirp4netns, which is transparent but may have
        slightly higher latency than Docker's host bridge mode. This is a Podman architectural
        limitation and does not affect functionality.

        Args:
            engine: Optional container engine ("docker" or "podman").
                   Defaults to Docker if not specified or TSDBENV_ENGINE not set.
                   Can also be set via TSDBENV_ENGINE environment variable.

        Raises:
            RuntimeError: If the engine socket is not accessible or engine is not running.
            ValueError: If engine value is invalid (not "docker" or "podman").

        Example:
            # Use default Docker
            client = DockerClient()

            # Explicitly use Podman
            client = DockerClient(engine="podman")

            # Or via environment variable
            export TSDBENV_ENGINE=podman
            client = DockerClient()
        """
        # Resolve engine from CLI/env/default
        engine_obj = get_engine_from_cli_or_env(engine)
        self._engine = engine_obj

        # Initialize client: Docker via docker.from_env() (honors DOCKER_HOST),
        # Podman via explicit socket path or DOCKER_HOST fallback
        try:
            if engine_obj == Engine.DOCKER:
                # Use docker.from_env() to honor DOCKER_HOST, Docker contexts, rootless Docker, Colima, etc.
                self.client = docker.from_env()
            else:
                # Podman: try standard socket path first, then DOCKER_HOST (for macOS Podman machine)
                import os
                from pathlib import Path

                socket_path = get_socket_path(engine_obj)
                if Path(socket_path).exists():
                    self.client = docker.DockerClient(base_url=f"unix://{socket_path}")
                else:
                    # Fallback to DOCKER_HOST (macOS with Podman machine)
                    docker_host = os.environ.get("DOCKER_HOST")
                    if docker_host:
                        self.client = docker.DockerClient(base_url=docker_host)
                    else:
                        # No socket and no DOCKER_HOST, try anyway
                        self.client = docker.DockerClient(
                            base_url=f"unix://{socket_path}"
                        )
        except Exception as e:
            engine_name = engine_obj.value.capitalize()
            raise RuntimeError(
                f"{engine_name} is not running or not installed. "
                f"Install with: brew install {engine_obj.value}"
            ) from e

        self._verify_docker()

    def check_docker_installed(self) -> bool:
        """Check if Docker daemon is running and accessible."""
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def _verify_docker(self) -> None:
        """Verify Docker is running; raise RuntimeError if not."""
        if not self.check_docker_installed():
            engine_name = self._engine.value.capitalize()
            raise RuntimeError(
                f"{engine_name} is not running or not accessible. "
                f"Install with: brew install {self._engine.value}"
            )

    def build_image(
        self,
        dockerfile_dir: str,
        tag: str,
        build_args: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build a Docker image from a Dockerfile.

        Args:
            dockerfile_dir: Directory containing Dockerfile
            tag: Image tag (e.g., "myapp:1.0")
            build_args: Build arguments passed to docker build (optional)

        Returns:
            Image ID

        Raises:
            RuntimeError: If build fails
        """
        try:
            image, build_logs = self.client.images.build(
                path=dockerfile_dir,
                tag=tag,
                buildargs=build_args or {},
                rm=True,  # Remove intermediate containers
            )
            return image.id
        except docker.errors.BuildError as e:
            raise RuntimeError(f"Docker build failed: {e}")

    def image_exists(self, tag: str) -> bool:
        """Return whether an image tag already exists in the local engine."""
        try:
            self.client.images.get(tag)
            return True
        except docker.errors.ImageNotFound:
            return False

    def prepare_image(
        self,
        tag: str,
        dockerfile_dir: str,
        build_args: Optional[Dict[str, str]] = None,
        rebuild: bool = False,
        pull: bool = True,
    ) -> str:
        """Reuse, pull, or build an image in fastest-first order.

        Existing local images are reused unless ``rebuild`` is requested. On a
        cache miss, a prebuilt registry image is pulled when ``pull`` is true.
        If pulling is disabled or unavailable, the image is built locally.
        """
        if not rebuild and self.image_exists(tag):
            return self.client.images.get(tag).id

        if not rebuild and pull:
            try:
                return self.client.images.pull(tag).id
            except docker.errors.APIError:
                pass

        build_args = dict(build_args or {})
        if "PG_VERSION" in build_args and "TS_VERSION" in build_args:
            build_args["BASE_IMAGE"] = self._timescale_base_image(
                build_args["PG_VERSION"]
            )
        return self.build_image(
            dockerfile_dir=dockerfile_dir,
            tag=tag,
            build_args=build_args,
        )

    @staticmethod
    def _timescale_base_image(postgres_version: str) -> str:
        """Find an HA image containing the exact requested PostgreSQL patch."""
        repository = "timescale/timescaledb-ha"
        if "." not in postgres_version:
            return f"{repository}:pg{postgres_version}"

        prefix = f"pg{postgres_version}-ts"
        url = f"https://hub.docker.com/v2/repositories/{repository}/tags/"
        try:
            response = requests.get(
                url, params={"page_size": 100, "name": prefix}, timeout=10
            )
            response.raise_for_status()
            names = [item["name"] for item in response.json().get("results", [])]
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise RuntimeError("Could not list TimescaleDB HA image tags") from exc

        pattern = re.compile(rf"{re.escape(prefix)}(\d+)\.(\d+)\.(\d+)$")
        candidates = []
        for name in names:
            match = pattern.fullmatch(name)
            if match:
                candidates.append((tuple(map(int, match.groups())), name))
        if not candidates:
            raise RuntimeError(
                f"No TimescaleDB HA image contains PostgreSQL {postgres_version}"
            )
        return f"{repository}:{max(candidates)[1]}"

    def create_container(
        self,
        image: str,
        name: str,
        environment: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[int, int]] = None,
        volumes: Optional[Dict] = None,
        tsdbadmin_password: Optional[str] = None,
        bind_ip: Optional[str] = None,
    ) -> str:
        """Create and start a PostgreSQL + TimescaleDB container.

        Args:
            image: Docker image name (e.g., "postgres:14-alpine")
            name: Container name
            environment: Environment variables dict
            ports: Port mapping {internal: external} (e.g., {5432: 5432})
            volumes: Volume mounts (optional)
            tsdbadmin_password: Password for tsdbadmin user (optional)
            bind_ip: IP address to bind container to (default: 127.0.0.1 for security)

        Returns:
            Container ID (short or long hash)

        Raises:
            docker.errors.APIError: If port is already in use or other Docker errors
        """
        try:
            env = environment or {}
            if tsdbadmin_password:
                env["TSDBADMIN_PASSWORD"] = tsdbadmin_password

            # Secure port binding: default to localhost only if not specified
            bind_ip = bind_ip or "127.0.0.1"

            # Convert ports dict to Docker SDK format: {internal: (bind_ip, external)}
            docker_ports = {}
            if ports:
                for internal_port, external_port in ports.items():
                    docker_ports[f"{internal_port}/tcp"] = (bind_ip, external_port)

            container = self.client.containers.run(
                image,
                name=name,
                environment=env,
                ports=docker_ports or {},
                volumes=volumes or {},
                detach=True,
                remove=False,  # Keep container even if stopped
                hostname=name,
            )
            # Wait for PostgreSQL to be ready
            self.wait_for_postgres(container.id)
            return container.id
        except docker.errors.APIError as e:
            if "Address already in use" in str(e):
                raise docker.errors.APIError(
                    "Port already in use; try a different port"
                )
            raise

    def start_container(self, container_id: str) -> None:
        """Start a stopped container."""
        container = self.client.containers.get(container_id)
        container.start()

    def stop_container(self, container_id: str) -> None:
        """Gracefully stop a running container."""
        container = self.client.containers.get(container_id)
        container.stop(timeout=10)

    def remove_container(self, container_id: str) -> None:
        """Remove a container (stop first if running)."""
        try:
            container = self.client.containers.get(container_id)
            if container.status in ["running", "paused"]:
                container.stop(timeout=10)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass

    def get_container_logs(self, container_id: str) -> str:
        """Get container logs (stdout/stderr)."""
        container = self.client.containers.get(container_id)
        return container.logs(stdout=True, stderr=True).decode("utf-8")

    def list_containers(self) -> List[Dict]:
        """List all containers (running + stopped).

        Returns:
            List of dicts: [{'id': ..., 'name': ..., 'status': ..., 'ports': ...}, ...]
        """
        containers = self.client.containers.list(all=True)
        result = []
        for c in containers:
            result.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "ports": c.ports,
                }
            )
        return result

    def wait_for_postgres(self, container_id: str, timeout: int = 30) -> bool:
        """Wait until PostgreSQL and all required extensions are ready.

        Args:
            container_id: Container ID
            timeout: Max seconds to wait

        Returns:
            True if ready, False if timeout

        Raises:
            TimeoutError: If PostgreSQL doesn't start within timeout
        """
        container = self.client.containers.get(container_id)
        extension_names = ", ".join(
            f"'{extension}'" for extension in self.REQUIRED_EXTENSIONS
        )
        readiness_query = (
            "SELECT count(*) FROM pg_extension "
            f"WHERE extname IN ({extension_names});"
        )
        expected_count = str(len(self.REQUIRED_EXTENSIONS))
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                container.reload()
                if container.status in ("exited", "dead"):
                    logs = container.logs(stdout=True, stderr=True).decode("utf-8")
                    raise RuntimeError(
                        f"Container exited before PostgreSQL was ready:\n{logs}"
                    )

                result = container.exec_run(
                    [
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "tsdb",
                        "-tAc",
                        readiness_query,
                    ],
                    user="postgres",
                )
                output = result.output.decode("utf-8").strip()
                if result.exit_code == 0 and output == expected_count:
                    return True
            except RuntimeError:
                raise
            except Exception:
                pass
            time.sleep(1)
        raise TimeoutError(
            f"PostgreSQL and required extensions not ready after {timeout}s"
        )

    def create_tablespaces(
        self, container_id: str, tablespace_names: List[str]
    ) -> Dict[str, bool]:
        """Create tablespaces in container.

        Args:
            container_id: Container ID
            tablespace_names: List of tablespace names

        Returns:
            Dict mapping tablespace name to success status
        """
        container = self.client.containers.get(container_id)
        results = {}

        for ts_name in tablespace_names:
            ts_path = f"/var/lib/postgresql/{ts_name}"
            try:
                # Create directory
                container.exec_run(f"mkdir -p {ts_path}", user="root")
                # Set ownership to postgres
                container.exec_run(f"chown postgres:postgres {ts_path}", user="root")
                # Set permissions to 700
                container.exec_run(f"chmod 700 {ts_path}", user="root")

                # Create tablespace in PostgreSQL (use postgres user, guaranteed to exist)
                result = container.exec_run(
                    f"psql -U postgres -d tsdb -c \"CREATE TABLESPACE {ts_name} LOCATION '{ts_path}';\"",
                    user="postgres",
                )
                if result.exit_code == 0:
                    results[ts_name] = True
                else:
                    results[ts_name] = False
            except Exception:
                results[ts_name] = False

        return results

    def execute_sql_file(
        self, container_id: str, sql_file_path: str, database: str = "tsdb"
    ) -> str:
        """Execute SQL file in container via psql.

        Args:
            container_id: Container ID
            sql_file_path: Path to SQL file on host
            database: Database to connect to

        Returns:
            Command output

        Raises:
            RuntimeError: If execution fails
        """
        sql_content = Path(sql_file_path).read_text()
        container = self.client.containers.get(container_id)

        # Copy SQL file to container
        import io
        import tarfile

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            info = tarfile.TarInfo(name="init.sql")
            info.size = len(sql_content)
            tar.addfile(tarinfo=info, fileobj=io.BytesIO(sql_content.encode()))
        tar_stream.seek(0)
        container.put_archive("/tmp", tar_stream)

        # Wait for PostgreSQL to accept connections before executing SQL
        start = time.time()
        timeout = 30
        while time.time() - start < timeout:
            result = container.exec_run("pg_isready -U postgres")
            if result.exit_code == 0:
                break
            time.sleep(1)
        else:
            raise TimeoutError("PostgreSQL not ready after 30s")

        # Execute SQL file (use postgres user, guaranteed to exist at this point)
        result = container.exec_run(
            f"psql -U postgres -d {database} -f /tmp/init.sql",
            user="postgres",
        )
        if result.exit_code != 0:
            error_msg = result.output.decode() if result.output else "Unknown error"
            raise RuntimeError(f"SQL execution failed: {error_msg}")
        return result.output.decode() if result.output else ""
