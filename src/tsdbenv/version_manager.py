# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from tsdbenv.models import VersionMatrix


class VersionManager:
    """Manages PostgreSQL × TimescaleDB compatibility matrix."""

    CACHE_FILE = "version_matrix.json"
    CACHE_MAX_AGE_HOURS = 24
    FALLBACK_MATRIX = {
        "12": ["2.5.0", "2.6.0", "2.7.0"],
        "13": ["2.6.0", "2.7.0", "2.8.0"],
        "14": ["2.8.0", "2.9.0", "2.10.0"],
        "15": ["2.9.0", "2.10.0", "2.11.0"],
        "16": ["2.26.0", "2.27.0", "2.28.0", "2.29.0", "2.29.1", "2.29.2"],
        "17": ["2.26.0", "2.27.0", "2.28.0", "2.29.0", "2.29.1", "2.29.2"],
        "18": ["2.26.0", "2.27.0", "2.28.0", "2.29.0", "2.29.1", "2.29.2"],
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize VersionManager.

        Args:
            cache_dir: Directory for caching matrix (default: ~/.tsdbenv)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".tsdbenv"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.matrix: Optional[VersionMatrix] = None

    def is_compatible(self, postgres_ver: str, timescaledb_ver: str) -> bool:
        """Check if versions are compatible."""
        if self.matrix is None:
            self.matrix = self.get_or_fetch()
        return self.matrix.is_compatible(postgres_ver, timescaledb_ver)

    def get_compatible_timescaledb_versions(self, postgres_ver: str) -> list:
        """Get compatible TimescaleDB versions for a PostgreSQL version."""
        if self.matrix is None:
            self.matrix = self.get_or_fetch()
        return self.matrix.postgres_versions.get(postgres_ver, [])

    def load_from_cache(self) -> Optional[VersionMatrix]:
        """Load compatibility matrix from cache file."""
        cache_file = self.cache_dir / self.CACHE_FILE
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text())
            return VersionMatrix(
                postgres_versions=data["matrix"],
                last_fetched=datetime.fromisoformat(data["fetched_at"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def fetch_from_docker_hub(self) -> VersionMatrix:
        """Fetch TimescaleDB × PostgreSQL compatibility from Docker Hub."""
        try:
            url = "https://registry.hub.docker.com/v2/repositories/timescale/timescaledb/tags/?page_size=300"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            matrix: dict[str, list[str]] = {}
            for tag in data.get("results", []):
                name = tag.get("name", "")
                # Parse tags like: 2.29.2-pg18, latest-pg16-oss, 2.28.0-pg17
                match = re.search(r"(\d+\.\d+\.\d+)-pg(\d+)", name)
                if match:
                    tsdb_ver, pg_ver = match.groups()
                    if pg_ver not in matrix:
                        matrix[pg_ver] = []
                    if tsdb_ver not in matrix[pg_ver]:
                        matrix[pg_ver].append(tsdb_ver)

            # Sort versions descending (newest first)
            for pg_ver in matrix:
                matrix[pg_ver].sort(
                    reverse=True, key=lambda x: tuple(map(int, x.split(".")))
                )

            # Merge with fallback: combine versions for shared PG versions
            merged_matrix = dict(self.FALLBACK_MATRIX)
            for pg_ver, tsdb_versions in matrix.items():
                if pg_ver in merged_matrix:
                    # Combine and deduplicate versions
                    combined = list(set(merged_matrix[pg_ver] + tsdb_versions))
                    combined.sort(
                        reverse=True, key=lambda x: tuple(map(int, x.split(".")))
                    )
                    merged_matrix[pg_ver] = combined
                else:
                    merged_matrix[pg_ver] = tsdb_versions

            if matrix:
                return VersionMatrix(
                    postgres_versions=merged_matrix, last_fetched=datetime.now()
                )
            return self._fallback_matrix()
        except (requests.RequestException, json.JSONDecodeError, KeyError):
            return self._fallback_matrix()

    def _fallback_matrix(self) -> VersionMatrix:
        """Return fallback matrix when fetch fails."""
        return VersionMatrix(
            postgres_versions=self.FALLBACK_MATRIX,
            last_fetched=datetime.now(),
        )

    def refresh(self) -> VersionMatrix:
        """Fetch latest matrix from Docker Hub and cache it."""
        matrix = self.fetch_from_docker_hub()
        self._save_to_cache(matrix)
        self.matrix = matrix
        return matrix

    def _is_cache_stale(self, cached: VersionMatrix) -> bool:
        """Check if cached matrix is older than CACHE_MAX_AGE_HOURS."""
        if cached.last_fetched is None:
            return True
        age = datetime.now() - cached.last_fetched
        return age.total_seconds() > (self.CACHE_MAX_AGE_HOURS * 3600)

    def get_or_fetch(self, auto_refresh_stale: bool = True) -> VersionMatrix:
        """Get matrix from cache, or fetch if unavailable or stale.

        Args:
            auto_refresh_stale: Refresh cache if older than CACHE_MAX_AGE_HOURS
        """
        cached = self.load_from_cache()
        if cached is not None:
            if auto_refresh_stale and self._is_cache_stale(cached):
                return self.refresh()
            self.matrix = cached
            return cached
        return self.refresh()

    def _save_to_cache(self, matrix: VersionMatrix) -> None:
        """Save matrix to cache file."""
        cache_file = self.cache_dir / self.CACHE_FILE
        data = {
            "matrix": matrix.postgres_versions,
            "fetched_at": matrix.last_fetched.isoformat(),
        }
        cache_file.write_text(json.dumps(data, indent=2))
