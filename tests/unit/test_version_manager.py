# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

import json
from datetime import datetime
from pathlib import Path

import pytest

from tsdbenv.models import VersionMatrix
from tsdbenv.version_manager import VersionManager


def test_version_manager_init(temp_state_dir):
    """Test VersionManager initialization."""
    vm = VersionManager(cache_dir=temp_state_dir)
    assert vm.cache_dir == temp_state_dir


def test_version_manager_is_compatible_true(sample_version_matrix, temp_state_dir):
    """Test is_compatible returns True for valid combo."""
    vm = VersionManager(cache_dir=temp_state_dir)
    vm.matrix = sample_version_matrix
    assert vm.is_compatible("14", "2.8.0") is True


def test_version_manager_is_compatible_false(sample_version_matrix, temp_state_dir):
    """Test is_compatible returns False for invalid combo."""
    vm = VersionManager(cache_dir=temp_state_dir)
    vm.matrix = sample_version_matrix
    assert vm.is_compatible("14", "2.11.0") is False


def test_version_manager_load_from_cache(temp_state_dir, sample_version_matrix):
    """Test loading matrix from cache file."""
    cache_file = temp_state_dir / "version_matrix.json"
    cache_data = {
        "fetched_at": sample_version_matrix.last_fetched.isoformat(),
        "matrix": sample_version_matrix.postgres_versions,
    }
    cache_file.write_text(json.dumps(cache_data))

    vm = VersionManager(cache_dir=temp_state_dir)
    matrix = vm.load_from_cache()

    assert matrix is not None
    assert matrix.is_compatible("14", "2.8.0")


def test_version_manager_load_from_cache_not_found(temp_state_dir):
    """Test load_from_cache returns None if file doesn't exist."""
    vm = VersionManager(cache_dir=temp_state_dir)
    matrix = vm.load_from_cache()
    assert matrix is None


def test_version_manager_get_or_fetch_uses_cache(temp_state_dir, sample_version_matrix):
    """Test get_or_fetch uses cached matrix if available."""
    cache_file = temp_state_dir / "version_matrix.json"
    cache_data = {
        "fetched_at": sample_version_matrix.last_fetched.isoformat(),
        "matrix": sample_version_matrix.postgres_versions,
    }
    cache_file.write_text(json.dumps(cache_data))

    vm = VersionManager(cache_dir=temp_state_dir)
    matrix = vm.get_or_fetch()

    assert matrix is not None
    assert matrix.is_compatible("14", "2.8.0")


def test_version_manager_get_or_fetch_saves_cache_on_miss(
    temp_state_dir, sample_version_matrix
):
    """Test the initial compatibility fetch is cached for later commands."""
    vm = VersionManager(cache_dir=temp_state_dir)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(vm, "fetch_from_docker_hub", lambda: sample_version_matrix)
        matrix = vm.get_or_fetch()

    assert matrix == sample_version_matrix
    assert (temp_state_dir / "version_matrix.json").exists()
