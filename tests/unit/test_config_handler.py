# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

import tempfile
from pathlib import Path

import pytest

from tsdbenv.config_handler import ConfigHandler
from tsdbenv.models import PostgresConfig


def test_parse_simple_kv(temp_state_dir):
    """Test parsing simple key=value config."""
    config_file = temp_state_dir / "simple.conf"
    config_file.write_text("shared_buffers=256MB\nwork_mem=4MB\n")

    config = ConfigHandler.parse_simple_kv(config_file)

    assert config.is_valid is True
    assert config.raw_settings["shared_buffers"] == "256MB"
    assert config.raw_settings["work_mem"] == "4MB"
    assert config.source_file == str(config_file)


def test_parse_simple_kv_with_comments(temp_state_dir):
    """Test parsing simple KV with comments."""
    config_file = temp_state_dir / "simple.conf"
    config_file.write_text(
        "# Comment\nshared_buffers=256MB\n# Another comment\nwork_mem=4MB\n"
    )

    config = ConfigHandler.parse_simple_kv(config_file)

    assert config.is_valid is True
    assert len(config.raw_settings) == 2


@pytest.mark.parametrize("parser_name", ["parse_simple_kv", "parse_postgresql_conf"])
def test_config_parsers_strip_inline_comments_but_keep_quoted_hashes(
    temp_state_dir, parser_name
):
    config_file = temp_state_dir / "inline-comments.conf"
    config_file.write_text(
        "work_mem = 77MB  # test comment\n"
        "log_line_prefix = '%m #literal' # trailing comment\n",
        encoding="utf-8",
    )

    config = getattr(ConfigHandler, parser_name)(config_file)

    assert config.raw_settings["work_mem"] == "77MB"
    assert config.raw_settings["log_line_prefix"] == "'%m #literal'"


def test_parse_postgresql_conf(temp_state_dir):
    """Test parsing full postgresql.conf format."""
    config_file = temp_state_dir / "postgresql.conf"
    config_file.write_text(
        """
# PostgreSQL Configuration

shared_buffers = 256MB
work_mem = 4MB

# More settings
log_statement = 'all'
"""
    )

    config = ConfigHandler.parse_postgresql_conf(config_file)

    assert config.is_valid is True
    assert config.raw_settings["shared_buffers"] == "256MB"
    assert config.raw_settings["log_statement"] == "'all'"


def test_parse_file_auto_detect_simple_kv(temp_state_dir):
    """Test auto-detection of simple KV format."""
    config_file = temp_state_dir / "config.txt"
    config_file.write_text("shared_buffers=256MB\nwork_mem=4MB\n")

    config = ConfigHandler.parse_file(config_file)

    assert config.is_valid is True
    assert config.raw_settings["shared_buffers"] == "256MB"


def test_parse_file_strips_inline_comments(temp_state_dir):
    config_file = temp_state_dir / "config-with-inline-comment.conf"
    config_file.write_text("work_mem = 77MB # test comment\n", encoding="utf-8")

    config = ConfigHandler.parse_file(config_file)

    assert config.raw_settings["work_mem"] == "77MB"


def test_parse_file_not_found():
    """Test error handling for missing file."""
    with pytest.raises(FileNotFoundError):
        ConfigHandler.parse_file(Path("/nonexistent/config.conf"))


def test_config_to_env_dict(sample_postgres_config):
    """Test converting config to environment variables."""
    env_dict = sample_postgres_config.to_env_dict()

    assert env_dict["shared_buffers"] == "256MB"
    assert env_dict["work_mem"] == "4MB"
