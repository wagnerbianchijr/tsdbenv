# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-20

import os

import pytest

from tsdbenv.engine_config import (
    Engine,
    EngineConfig,
    get_engine_from_cli_or_env,
    get_socket_path,
)


class TestEngine:
    """Test Engine enum."""

    def test_engine_docker_value(self):
        """Test Engine.DOCKER has correct value."""
        assert Engine.DOCKER.value == "docker"

    def test_engine_podman_value(self):
        """Test Engine.PODMAN has correct value."""
        assert Engine.PODMAN.value == "podman"

    def test_engine_from_string(self):
        """Test creating Engine from string."""
        assert Engine("docker") == Engine.DOCKER
        assert Engine("podman") == Engine.PODMAN

    def test_engine_invalid_value(self):
        """Test Engine with invalid value raises ValueError."""
        with pytest.raises(ValueError):
            Engine("invalid")


class TestGetSocketPath:
    """Test get_socket_path() function."""

    def test_docker_socket_path(self):
        """Test Docker socket path."""
        assert get_socket_path(Engine.DOCKER) == "/var/run/docker.sock"

    def test_podman_socket_path(self):
        """Test Podman socket path is rootless format."""
        socket_path = get_socket_path(Engine.PODMAN)
        # Should be either /run/user/{uid}/podman/podman.sock (Linux rootless)
        # or /var/folders/*/T/podman/podman-machine-default-api.sock (macOS Podman Machine)
        uid = os.getuid()
        expected_linux = f"/run/user/{uid}/podman/podman.sock"
        is_macos_path = (
            socket_path.startswith("/var/folders")
            and "podman-machine-default-api.sock" in socket_path
        )
        is_linux_path = socket_path == expected_linux
        assert is_macos_path or is_linux_path


class TestGetEngineFromCliOrEnv:
    """Test get_engine_from_cli_or_env() function with precedence."""

    def test_cli_arg_takes_precedence_over_env(self, monkeypatch):
        """Test CLI arg overrides environment variable."""
        monkeypatch.setenv("TSDBENV_ENGINE", "podman")
        result = get_engine_from_cli_or_env(cli_engine="docker")
        assert result == Engine.DOCKER

    def test_env_var_used_when_no_cli_arg(self, monkeypatch):
        """Test TSDBENV_ENGINE env var is used when no CLI arg."""
        monkeypatch.setenv("TSDBENV_ENGINE", "podman")
        result = get_engine_from_cli_or_env()
        assert result == Engine.PODMAN

    def test_default_docker_when_no_cli_or_env(self, monkeypatch):
        """Test defaults to Docker when no CLI arg or env var."""
        monkeypatch.delenv("TSDBENV_ENGINE", raising=False)
        result = get_engine_from_cli_or_env()
        assert result == Engine.DOCKER

    def test_cli_arg_case_insensitive_docker(self):
        """Test CLI arg is case-insensitive for Docker."""
        assert get_engine_from_cli_or_env(cli_engine="Docker") == Engine.DOCKER
        assert get_engine_from_cli_or_env(cli_engine="DOCKER") == Engine.DOCKER
        assert get_engine_from_cli_or_env(cli_engine="dOcKeR") == Engine.DOCKER

    def test_cli_arg_case_insensitive_podman(self):
        """Test CLI arg is case-insensitive for Podman."""
        assert get_engine_from_cli_or_env(cli_engine="Podman") == Engine.PODMAN
        assert get_engine_from_cli_or_env(cli_engine="PODMAN") == Engine.PODMAN
        assert get_engine_from_cli_or_env(cli_engine="pOdMaN") == Engine.PODMAN

    def test_env_var_case_insensitive(self, monkeypatch):
        """Test TSDBENV_ENGINE env var is case-insensitive."""
        monkeypatch.setenv("TSDBENV_ENGINE", "PODMAN")
        assert get_engine_from_cli_or_env() == Engine.PODMAN

    def test_cli_arg_with_whitespace(self):
        """Test CLI arg with leading/trailing whitespace."""
        assert get_engine_from_cli_or_env(cli_engine="  docker  ") == Engine.DOCKER
        assert get_engine_from_cli_or_env(cli_engine=" podman ") == Engine.PODMAN

    def test_invalid_cli_arg(self):
        """Test invalid CLI arg raises ValueError."""
        with pytest.raises(ValueError, match="Invalid engine"):
            get_engine_from_cli_or_env(cli_engine="kubernetes")

    def test_invalid_env_var(self, monkeypatch):
        """Test invalid TSDBENV_ENGINE value raises ValueError."""
        monkeypatch.setenv("TSDBENV_ENGINE", "invalid_engine")
        with pytest.raises(ValueError, match="Invalid TSDBENV_ENGINE"):
            get_engine_from_cli_or_env()

    def test_empty_cli_arg(self, monkeypatch):
        """Test empty CLI arg is treated as None (defaults to Docker)."""
        monkeypatch.delenv("TSDBENV_ENGINE", raising=False)
        # Empty string should fail validation
        with pytest.raises(ValueError):
            get_engine_from_cli_or_env(cli_engine="")


class TestEngineConfig:
    """Test EngineConfig dataclass."""

    def test_engine_config_creation_docker(self):
        """Test creating EngineConfig with Docker."""
        config = EngineConfig(
            engine=Engine.DOCKER,
            socket_path="/var/run/docker.sock",
        )
        assert config.engine == Engine.DOCKER
        assert config.socket_path == "/var/run/docker.sock"

    def test_engine_config_creation_podman(self):
        """Test creating EngineConfig with Podman."""
        uid = os.getuid()
        socket_path = f"/run/user/{uid}/podman/podman.sock"
        config = EngineConfig(
            engine=Engine.PODMAN,
            socket_path=socket_path,
        )
        assert config.engine == Engine.PODMAN
        assert config.socket_path == socket_path


class TestEngineConfigFromEngine:
    """Test EngineConfig.from_engine() factory method."""

    def test_from_engine_docker(self):
        """Test creating EngineConfig from Engine.DOCKER."""
        config = EngineConfig.from_engine(Engine.DOCKER)
        assert config.engine == Engine.DOCKER
        assert config.socket_path == "/var/run/docker.sock"

    def test_from_engine_podman(self):
        """Test creating EngineConfig from Engine.PODMAN."""
        uid = os.getuid()
        expected_path = f"/run/user/{uid}/podman/podman.sock"
        config = EngineConfig.from_engine(Engine.PODMAN)
        assert config.engine == Engine.PODMAN
        # Socket path can be either Linux rootless or macOS Podman Machine
        is_macos_path = (
            config.socket_path.startswith("/var/folders")
            and "podman-machine-default-api.sock" in config.socket_path
        )
        is_linux_path = config.socket_path == expected_path
        assert is_macos_path or is_linux_path


class TestEngineConfigFromCliOrEnv:
    """Test EngineConfig.from_cli_or_env() factory method."""

    def test_from_cli_or_env_cli_docker(self, monkeypatch):
        """Test from_cli_or_env with CLI arg for Docker."""
        monkeypatch.delenv("TSDBENV_ENGINE", raising=False)
        config = EngineConfig.from_cli_or_env(cli_engine="docker")
        assert config.engine == Engine.DOCKER
        assert config.socket_path == "/var/run/docker.sock"

    def test_from_cli_or_env_cli_podman(self, monkeypatch):
        """Test from_cli_or_env with CLI arg for Podman."""
        monkeypatch.delenv("TSDBENV_ENGINE", raising=False)
        uid = os.getuid()
        expected_path = f"/run/user/{uid}/podman/podman.sock"
        config = EngineConfig.from_cli_or_env(cli_engine="podman")
        assert config.engine == Engine.PODMAN
        # Socket path can be either Linux rootless or macOS Podman Machine
        is_macos_path = (
            config.socket_path.startswith("/var/folders")
            and "podman-machine-default-api.sock" in config.socket_path
        )
        is_linux_path = config.socket_path == expected_path
        assert is_macos_path or is_linux_path

    def test_from_cli_or_env_env_var_docker(self, monkeypatch):
        """Test from_cli_or_env with TSDBENV_ENGINE for Docker."""
        monkeypatch.setenv("TSDBENV_ENGINE", "docker")
        config = EngineConfig.from_cli_or_env()
        assert config.engine == Engine.DOCKER
        assert config.socket_path == "/var/run/docker.sock"

    def test_from_cli_or_env_env_var_podman(self, monkeypatch):
        """Test from_cli_or_env with TSDBENV_ENGINE for Podman."""
        monkeypatch.setenv("TSDBENV_ENGINE", "podman")
        uid = os.getuid()
        expected_path = f"/run/user/{uid}/podman/podman.sock"
        config = EngineConfig.from_cli_or_env()
        assert config.engine == Engine.PODMAN
        # Socket path can be either Linux rootless or macOS Podman Machine
        is_macos_path = (
            config.socket_path.startswith("/var/folders")
            and "podman-machine-default-api.sock" in config.socket_path
        )
        is_linux_path = config.socket_path == expected_path
        assert is_macos_path or is_linux_path

    def test_from_cli_or_env_defaults_to_docker(self, monkeypatch):
        """Test from_cli_or_env defaults to Docker when no CLI or env var."""
        monkeypatch.delenv("TSDBENV_ENGINE", raising=False)
        config = EngineConfig.from_cli_or_env()
        assert config.engine == Engine.DOCKER
        assert config.socket_path == "/var/run/docker.sock"

    def test_from_cli_or_env_cli_overrides_env(self, monkeypatch):
        """Test from_cli_or_env: CLI arg overrides env var."""
        monkeypatch.setenv("TSDBENV_ENGINE", "docker")
        uid = os.getuid()
        expected_path = f"/run/user/{uid}/podman/podman.sock"
        config = EngineConfig.from_cli_or_env(cli_engine="podman")
        assert config.engine == Engine.PODMAN
        # Socket path can be either Linux rootless or macOS Podman Machine
        is_macos_path = (
            config.socket_path.startswith("/var/folders")
            and "podman-machine-default-api.sock" in config.socket_path
        )
        is_linux_path = config.socket_path == expected_path
        assert is_macos_path or is_linux_path

    def test_from_cli_or_env_invalid_cli(self, monkeypatch):
        """Test from_cli_or_env with invalid CLI arg."""
        monkeypatch.delenv("TSDBENV_ENGINE", raising=False)
        with pytest.raises(ValueError, match="Invalid engine"):
            EngineConfig.from_cli_or_env(cli_engine="invalid")

    def test_from_cli_or_env_invalid_env(self, monkeypatch):
        """Test from_cli_or_env with invalid env var."""
        monkeypatch.setenv("TSDBENV_ENGINE", "invalid")
        with pytest.raises(ValueError, match="Invalid TSDBENV_ENGINE"):
            EngineConfig.from_cli_or_env()
