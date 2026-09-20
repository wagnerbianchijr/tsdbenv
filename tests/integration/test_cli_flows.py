# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

import pytest
from click.testing import CliRunner

from tsdbenv.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_cli_version(cli_runner):
    """Test --version flag."""
    result = cli_runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "tsdbenv" in result.output


def test_cli_help(cli_runner):
    """Test --help flag."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "PostgreSQL" in result.output
    assert "TimescaleDB" in result.output


def test_cli_subcommand_help(cli_runner):
    """Test subcommand help."""
    result = cli_runner.invoke(main, ["new", "--help"])
    assert result.exit_code == 0
    assert "postgres" in result.output.lower()
    assert "--rebuild" in result.output
