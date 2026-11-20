# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tsdbenv.models import Container, VersionMatrix
from tsdbenv.state_tracker import StateTracker
from tsdbenv.version_manager import VersionManager


def test_full_lifecycle(temp_state_dir):
    """Test full container lifecycle: create → access → stale → remove."""
    st = StateTracker(state_dir=temp_state_dir)
    vm = VersionManager(cache_dir=temp_state_dir)

    assert vm.is_compatible("14", "2.8.0") is True

    container = Container(
        name="lifecycle_test",
        postgres_version="14",
        timescaledb_version="2.8.0",
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        config_path=None,
        docker_id="id123",
        port=5432,
        bind_ip="127.0.0.1",
        tsdbadmin_password="pwd",
    )
    st.save_container(container)

    containers = st.load_containers()
    assert len(containers) == 1
    assert containers[0].name == "lifecycle_test"

    st.mark_accessed("lifecycle_test")
    stale_list = st.get_stale_containers(days=5)
    assert len(stale_list) == 0

    containers = st.load_containers()
    containers[0].last_accessed_at = datetime.now() - timedelta(days=6)
    st.save_container(containers[0])

    stale_list = st.get_stale_containers(days=5)
    assert len(stale_list) == 1

    st.delete_container("lifecycle_test")
    containers = st.load_containers()
    assert len(containers) == 0


def test_version_compatibility_flow(temp_state_dir):
    """Test version compatibility validation flow."""
    vm = VersionManager(cache_dir=temp_state_dir)
    vm.matrix = VersionMatrix(
        postgres_versions=VersionManager.FALLBACK_MATRIX,
        last_fetched=datetime.now(),
    )

    assert vm.is_compatible("14", "2.8.0") is True
    assert vm.is_compatible("15", "2.9.0") is True

    assert vm.is_compatible("14", "2.11.0") is False
    assert vm.is_compatible("99", "2.8.0") is False


def test_state_persistence(temp_state_dir):
    """Test that state persists across StateTracker instances."""
    st1 = StateTracker(state_dir=temp_state_dir)
    c1 = Container(
        name="persist_test",
        postgres_version="14",
        timescaledb_version="2.8.0",
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        config_path=None,
        docker_id="id456",
        port=5432,
        bind_ip="127.0.0.1",
        tsdbadmin_password="pwd",
    )
    st1.save_container(c1)

    st2 = StateTracker(state_dir=temp_state_dir)
    containers = st2.load_containers()
    assert len(containers) == 1
    assert containers[0].name == "persist_test"
