import os
import subprocess
import sys

from tsdbenv.environment import load_environment


def test_load_environment_from_directory(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("TSDBENV_ENGINE=podman\n")
    monkeypatch.delenv("TSDBENV_ENGINE", raising=False)

    assert load_environment(tmp_path) is True
    assert os.environ["TSDBENV_ENGINE"] == "podman"


def test_load_environment_preserves_exported_value(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("TSDBENV_ENGINE=podman\n")
    monkeypatch.setenv("TSDBENV_ENGINE", "docker")

    assert load_environment(tmp_path) is True
    assert os.environ["TSDBENV_ENGINE"] == "docker"


def test_load_environment_allows_missing_file(tmp_path, monkeypatch):
    monkeypatch.delenv("TSDBENV_ENGINE", raising=False)

    assert load_environment(tmp_path) is False


def test_cli_import_loads_environment_from_working_directory(tmp_path):
    (tmp_path / ".env").write_text("TSDBENV_ENGINE=podman\n")
    environment = os.environ.copy()
    environment.pop("TSDBENV_ENGINE", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import tsdbenv.cli; print(os.environ['TSDBENV_ENGINE'])",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "podman"
