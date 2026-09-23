# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Container(BaseModel):
    """Represents a PostgreSQL + TimescaleDB container."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "mydb",
                "postgres_version": "14",
                "timescaledb_version": "2.8.0",
                "created_at": "2026-08-19T10:00:00Z",
                "last_accessed_at": "2026-08-19T14:00:00Z",
                "config_path": None,
                "docker_id": "abc123",
                "port": 5432,
                "bind_ip": "127.0.0.1",
                "tsdbadmin_password": "secure_pwd",
                "engine": "docker",
            }
        }
    )

    name: str = Field(..., description="Unique container identifier")
    postgres_version: str = Field(..., description="PostgreSQL version (e.g., '14')")
    timescaledb_version: str = Field(
        ..., description="TimescaleDB version (e.g., '2.8.0')"
    )
    created_at: datetime = Field(..., description="Container creation timestamp")
    last_accessed_at: datetime = Field(
        ..., description="Last user interaction timestamp"
    )
    config_path: Optional[str] = Field(
        None, description="Path to PostgreSQL config file"
    )
    docker_id: str = Field(..., description="Docker container ID")
    port: int = Field(default=5432, description="PostgreSQL port")
    bind_ip: str = Field(default="127.0.0.1", description="IP to bind container to")
    tsdbadmin_password: str = Field(..., description="tsdbadmin user password")
    engine: str = Field(
        default="docker", description="Container engine (docker or podman)"
    )


class VersionMatrix(BaseModel):
    """Compatibility matrix: PostgreSQL versions → compatible TimescaleDB versions."""

    postgres_versions: Dict[str, List[str]] = Field(
        ..., description="Map of PG version → list of compatible TS versions"
    )
    last_fetched: datetime = Field(..., description="When matrix was last fetched")

    def is_compatible(self, postgres_ver: str, timescaledb_ver: str) -> bool:
        """Check if postgres_ver and timescaledb_ver are compatible."""
        if postgres_ver not in self.postgres_versions:
            return False
        return timescaledb_ver in self.postgres_versions[postgres_ver]


class PostgresConfig(BaseModel):
    """PostgreSQL configuration (key=value pairs)."""

    raw_settings: Dict[str, str] = Field(
        default_factory=dict, description="PostgreSQL settings (key=value)"
    )
    source_file: Optional[str] = Field(None, description="Source file path")
    is_valid: bool = Field(default=True, description="Whether config passed validation")

    def to_env_dict(self) -> Dict[str, str]:
        """Convert settings to environment variable format (for Docker)."""
        return self.raw_settings.copy()
