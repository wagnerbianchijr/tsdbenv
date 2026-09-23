# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-20

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Engine(str, Enum):
    """Container engine selection: Docker or Podman."""

    DOCKER = "docker"
    PODMAN = "podman"


def get_socket_path(engine: Engine) -> str:
    """
    Get socket path for the specified container engine.

    For Docker, returns the standard socket path. For Podman, derives the rootless
    socket path from XDG_RUNTIME_DIR and UID.

    Args:
        engine: Engine.DOCKER or Engine.PODMAN

    Returns:
        Socket path string. For Docker: /var/run/docker.sock (or honors DOCKER_HOST).
        For rootless Podman: /run/user/{uid}/podman/podman.sock on Linux,
        or machine socket path on macOS.

    Raises:
        RuntimeError: If Podman socket path cannot be determined.
    """
    if engine == Engine.DOCKER:
        return "/var/run/docker.sock"

    # For Podman: determine rootless socket path
    if engine == Engine.PODMAN:
        # Try XDG_RUNTIME_DIR-based path (Linux rootless)
        xdg_runtime = os.getenv("XDG_RUNTIME_DIR")
        if xdg_runtime:
            socket_path = f"{xdg_runtime}/podman/podman.sock"
            if Path(socket_path).exists():
                return socket_path

        # Try macOS Podman Machine socket path (/var/folders/...)
        import glob

        macos_machine_sockets = glob.glob(
            "/var/folders/*/*/T/podman/podman-machine-default-api.sock"
        )
        if macos_machine_sockets:
            return macos_machine_sockets[0]

        # Fallback: /run/user/{uid}/podman/podman.sock (Linux rootless default)
        uid = os.getuid()
        linux_rootless_path = f"/run/user/{uid}/podman/podman.sock"
        if Path(linux_rootless_path).exists():
            return linux_rootless_path

        # macOS: socket is typically managed by podman machine
        # Return the Linux path and let the connection attempt fail with helpful error
        return linux_rootless_path

    raise RuntimeError(f"Unknown engine: {engine}")


def get_engine_from_cli_or_env(cli_engine: Optional[str] = None) -> Engine:
    """
    Determine container engine from CLI arg or environment variable.

    Precedence: explicit CLI arg > TSDBENV_ENGINE env var > default (Docker).

    Args:
        cli_engine: Optional engine name from CLI (--engine flag).
                   Accepts "docker" or "podman" (case-insensitive).

    Returns:
        Engine.DOCKER or Engine.PODMAN

    Raises:
        ValueError: If cli_engine is provided but is invalid.
    """
    # 1. Check explicit CLI argument
    if cli_engine is not None:
        cli_engine_lower = cli_engine.lower().strip()
        try:
            return Engine(cli_engine_lower)
        except ValueError:
            raise ValueError(
                f"Invalid engine '{cli_engine}'. Must be 'docker' or 'podman'."
            )

    # 2. Check environment variable
    env_engine = os.getenv("TSDBENV_ENGINE")
    if env_engine is not None:
        env_engine_lower = env_engine.lower().strip()
        try:
            return Engine(env_engine_lower)
        except ValueError:
            raise ValueError(
                f"Invalid TSDBENV_ENGINE value '{env_engine}'. "
                f"Must be 'docker' or 'podman'."
            )

    # 3. Default to Docker
    return Engine.DOCKER


@dataclass
class EngineConfig:
    """Configuration for container engine (Docker or Podman)."""

    engine: Engine
    socket_path: str

    def __post_init__(self):
        """Validate and set socket_path based on engine if not provided."""
        if not self.socket_path:
            self.socket_path = get_socket_path(self.engine)

    @staticmethod
    def from_engine(engine: Engine) -> "EngineConfig":
        """
        Create EngineConfig from an Engine enum.

        Args:
            engine: Engine.DOCKER or Engine.PODMAN

        Returns:
            EngineConfig instance with socket_path set
        """
        socket_path = get_socket_path(engine)
        return EngineConfig(
            engine=engine,
            socket_path=socket_path,
        )

    @staticmethod
    def from_cli_or_env(cli_engine: Optional[str] = None) -> "EngineConfig":
        """
        Create EngineConfig from CLI arg or environment variable.

        Uses precedence: CLI > TSDBENV_ENGINE env var > Docker (default).

        Args:
            cli_engine: Optional engine name from CLI.

        Returns:
            EngineConfig instance with appropriate engine and defaults

        Raises:
            ValueError: If engine selection is invalid
        """
        engine = get_engine_from_cli_or_env(cli_engine)
        return EngineConfig.from_engine(engine)
