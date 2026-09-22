# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

import hashlib
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import click
from click.formatting import HelpFormatter
from tabulate import tabulate

from tsdbenv import __version__
from tsdbenv.config_handler import ConfigHandler
from tsdbenv.docker_utils import DockerClient
from tsdbenv.engine_config import Engine
from tsdbenv.environment import load_environment
from tsdbenv.models import Container
from tsdbenv.network_validator import NetworkValidator
from tsdbenv.state_tracker import StateTracker
from tsdbenv.utils import ensure_state_dir, generate_password
from tsdbenv.version_manager import VersionManager

load_environment()


class Spinner:
    """Simple terminal spinner for non-verbose mode."""

    def __init__(self, message: str):
        self.message = message
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current = 0
        self.running = False
        self.thread = None
        self.started_at = 0.0
        self.rendered_width = 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def start(self):
        self.started_at = time.monotonic()
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        # Clear the spinner line
        click.echo("\r" + " " * self.rendered_width, nl=False)
        click.echo("\r", nl=False)

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        elapsed = max(0, int(seconds))
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _spin(self):
        while self.running:
            char = self.spinner_chars[self.current % len(self.spinner_chars)]
            elapsed = self._format_elapsed(time.monotonic() - self.started_at)
            line = f"{char} {self.message} [{elapsed}]"
            self.rendered_width = max(self.rendered_width, len(line))
            click.echo(f"\r{line}", nl=False)
            sys.stdout.flush()
            self.current += 1
            time.sleep(0.1)


def log(message: str) -> None:
    """Log message with ISO 8601 timestamp (only if verbose mode enabled)."""
    if cli_state.verbose:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"{ts} {message}")


def spinner(message: str):
    """Context manager for spinner in non-verbose mode."""
    if cli_state.verbose:
        return _NoOpContext()
    return Spinner(message)


class _NoOpContext:
    """Context manager that does nothing."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class CustomGroup(click.Group):
    """Custom group to format command help with short flags."""

    def format_commands(self, ctx, formatter):
        """Writes all the commands to the formatter."""
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None:
                continue

            short_flags = {
                "new": "-n",
                "list": "-l",
                "logs": None,
                "remove": "-r",
                "removeall": "-a",
                "connectstring": "-c",
                "tablespaces": "-t",
                "versionrefresh": "-g",
                "matrix": "-m",
            }

            help_text = cmd.get_short_help_str(100)
            flag = short_flags.get(subcommand)

            if flag:
                help_text = f"{flag}, {help_text}"

            commands.append((subcommand, help_text))

        if commands:
            with formatter.section("Commands"):
                formatter.write_dl(commands)


def _expand_short_aliases():
    """Expand -n, -l, -c, -g, -m, -a, -t to full command names."""
    if len(sys.argv) <= 1:
        return

    # Move --engine/-e to the front if present but not already there
    for i in range(1, len(sys.argv)):
        if sys.argv[i] in ("--engine", "-e") and i > 1:
            # Found engine flag after position 1, move it and its value to the front
            if i + 1 < len(sys.argv):
                engine_flag = sys.argv[i]
                engine_value = sys.argv[i + 1]
                # Remove from current position
                sys.argv.pop(i + 1)
                sys.argv.pop(i)
                # Insert at position 1
                sys.argv.insert(1, engine_value)
                sys.argv.insert(1, engine_flag)
            break

    aliases = {
        "-n": "new",
        "-l": "list",
        "-r": "remove",
        "-c": "connectstring",
        "-g": "versionrefresh",
        "-m": "matrix",
        "-a": "removeall",
        "-t": "tablespaces",
    }

    # Find the first positional argument (command) - skip option names and their values
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]

        # Skip option values
        if arg in ("--engine", "-e"):
            i += 2  # Skip the option and its value
            continue

        # If it starts with - but isn't a known option, it's a short command alias
        if arg.startswith("-") and not arg.startswith("--"):
            if arg in aliases:
                sys.argv[i] = aliases[arg]
                break
        elif not arg.startswith("-"):
            # Found first positional arg (command name), check if it's a short alias
            if arg in aliases:
                sys.argv[i] = aliases[arg]
            break

        i += 1


_expand_short_aliases()


def get_dockerfiles_dir() -> Path:
    """Get the path to the dockerfiles directory."""
    return Path(__file__).parent / "dockerfiles"


class CLIState:
    def __init__(self, engine: Engine = Engine.DOCKER, verbose: bool = False):
        self.engine = engine
        self.verbose = verbose
        self.state_dir = ensure_state_dir()
        self.state_tracker = StateTracker(state_dir=self.state_dir)
        self.version_manager = VersionManager(cache_dir=self.state_dir)
        self.docker_client: DockerClient | None = None
        try:
            self.docker_client = DockerClient(engine=engine.value)
        except RuntimeError:
            pass


cli_state = CLIState()


def init_cli_state(engine: Engine, verbose: bool = False) -> None:
    """Reinitialize CLI state with specified engine."""
    global cli_state
    cli_state = CLIState(engine=engine, verbose=verbose)
    if cli_state.docker_client is None:
        engine_name = engine.value.capitalize()
        click.echo(f"ERROR {engine_name} is not installed or not running.")
        if engine == Engine.DOCKER:
            click.echo("   Please install Docker: https://docs.docker.com/get-docker/")
        else:
            click.echo("   Please install Podman: https://podman.io/")
        raise click.Abort()


@click.command(
    cls=CustomGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.option("-v", "--version", is_flag=True, help="Show version and exit")
@click.option(
    "-e",
    "--engine",
    type=click.Choice(["docker", "podman"]),
    default="docker",
    envvar="TSDBENV_ENGINE",
    help="Container engine (default: docker, or TSDBENV_ENGINE env var)",
)
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def main(ctx, version, engine, verbose):
    """tsdbenv - PostgreSQL + TimescaleDB environment manager."""
    if version:
        click.echo(f"tsdbenv {__version__}")
        ctx.exit(0)
    init_cli_state(Engine(engine), verbose=verbose)
    if ctx.invoked_subcommand is None:
        show_interactive_menu()


@main.command()
@click.option("--postgres", help="PostgreSQL version (e.g., 15 or 15.18)")
@click.option("--timescaledb", help="TimescaleDB version (e.g., 2.8.0)")
@click.option("--port", type=int, default=None, help="PostgreSQL port")
@click.option("--config", type=click.Path(exists=True), help="PostgreSQL config file")
@click.option("--bind-ip", help="IP to bind to (default: 127.0.0.1)")
@click.option("-i", "--init", type=click.Path(exists=True), help="SQL file to execute")
@click.option("-t", "--tablespaces", help="Comma-separated tablespace names")
@click.option("--force", is_flag=True, help="Skip version compatibility check")
@click.option(
    "--rebuild",
    is_flag=True,
    help="Rebuild the local image instead of reusing a cached or prebuilt image",
)
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
def new(
    postgres,
    timescaledb,
    port,
    config,
    bind_ip,
    init,
    tablespaces,
    force,
    rebuild,
    verbose,
):
    """Create PostgreSQL + TimescaleDB container"""
    if verbose:
        cli_state.verbose = True
    with spinner("Loading TimescaleDB compatibility data..."):
        log("Loading TimescaleDB compatibility data...")
        cli_state.version_manager.get_or_fetch()

    if not postgres:
        postgres = click.prompt("PostgreSQL version", type=str)
    if not timescaledb:
        timescaledb = click.prompt("TimescaleDB version", type=str)

    if not re.fullmatch(r"\d+(?:\.\d+)?", postgres):
        raise click.BadParameter(
            "use a major or major.patch version", param_hint="--postgres"
        )
    if not re.fullmatch(r"\d+\.\d+\.\d+", timescaledb):
        raise click.BadParameter(
            "use a major.minor.patch release", param_hint="--timescaledb"
        )

    postgres_major = postgres.split(".", 1)[0]

    if not force and not cli_state.version_manager.is_compatible(
        postgres_major, timescaledb
    ):
        compatible_versions = (
            cli_state.version_manager.get_compatible_timescaledb_versions(
                postgres_major
            )
        )
        click.echo(
            f"ERROR TSDB {timescaledb} is not compatible with PostgreSQL {postgres}"
        )
        if compatible_versions:
            versions_str = ", ".join(compatible_versions)
            click.echo(f"   Compatible TSDB versions: {versions_str}")
        click.echo("   Use --force to override")
        raise click.Abort()

    timestamp_hash = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
    name = f"tsdb-{timestamp_hash}"

    if config:
        try:
            ConfigHandler.parse_file(Path(config))
        except Exception as e:
            click.echo(f"ERROR Failed to parse config: {e}")
            return

    if not bind_ip:
        bind_ip = "127.0.0.1"

    is_valid, warning = NetworkValidator.validate_bind_ip(bind_ip)
    if not is_valid:
        click.echo(warning)
        if not click.confirm("Continue anyway?"):
            return

    if port is None:
        port = NetworkValidator.find_available_port(bind_ip)

    tsdbadmin_password = generate_password()

    try:
        dockerfile_dir = str(get_dockerfiles_dir())
        image_tag = f"tsdbenv:pg{postgres}-ts{timescaledb}-v3"
        with spinner(
            f"Preparing PostgreSQL {postgres} + TimescaleDB {timescaledb} image..."
        ):
            log(f"Preparing PostgreSQL {postgres} + TimescaleDB {timescaledb} image...")
            cli_state.docker_client.prepare_image(
                tag=image_tag,
                dockerfile_dir=dockerfile_dir,
                build_args={"PG_VERSION": postgres, "TS_VERSION": timescaledb},
                rebuild=rebuild,
                pull=False,
            )
    except Exception as e:
        click.echo(f"ERROR Failed to prepare container image: {e}")
        raise click.Abort()

    with spinner(f"Creating container {name} and waiting for PostgreSQL..."):
        log(f"Creating container {name} and waiting for PostgreSQL...")
        container_id = cli_state.docker_client.create_container(
            image=image_tag,
            name=name,
            environment={
                "POSTGRES_PASSWORD": "postgres",
                "POSTGRESQL_PASSWORD": "postgres",
                "PGPASSWORD": "postgres",
            },
            ports={5432: port},
            tsdbadmin_password=tsdbadmin_password,
            bind_ip=bind_ip,
        )

    container = Container(
        name=name,
        postgres_version=postgres,
        timescaledb_version=timescaledb,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        config_path=config,
        docker_id=container_id,
        port=port,
        bind_ip=bind_ip,
        tsdbadmin_password=tsdbadmin_password,
        engine=cli_state.engine.value,
    )
    cli_state.state_tracker.save_container(container)

    if init:
        try:
            with spinner("Waiting for PostgreSQL to be fully ready..."):
                log("Waiting for PostgreSQL to be fully ready...")
                cli_state.docker_client.wait_for_postgres(container_id, timeout=60)
            with spinner("Executing init SQL file..."):
                log("Executing init SQL file...")
                cli_state.docker_client.execute_sql_file(container_id, init)
            log("Init SQL executed successfully")
        except Exception as e:
            click.echo(f"WARNING Init SQL execution failed: {e}")
            click.echo("   Container created but schema setup incomplete")

    if tablespaces:
        try:
            ts_list = [ts.strip() for ts in tablespaces.split(",")]
            with spinner(f"Creating {len(ts_list)} tablespace(s)..."):
                log(f"Creating {len(ts_list)} tablespace(s)...")
                results = cli_state.docker_client.create_tablespaces(
                    container_id, ts_list
                )
            successful = sum(1 for v in results.values() if v)
            log(f"Created {successful}/{len(ts_list)} tablespace(s)")
            if successful < len(ts_list):
                failed = [k for k, v in results.items() if not v]
                click.echo(f"   WARNING Failed: {', '.join(failed)}")
        except Exception as e:
            click.echo(f"WARNING Tablespace creation failed: {e}")
            click.echo("   Container created but tablespaces incomplete")

    display_connection_info(container)


@main.command("list")
def list_cmd():
    """List all containers"""
    containers = cli_state.state_tracker.load_containers()
    if not containers:
        click.echo("No containers found.")
        return

    stale = cli_state.state_tracker.get_stale_containers(days=5)
    for s in stale:
        if click.confirm(f"Container '{s.name}' unused for 5+ days. Remove?"):
            cli_state.state_tracker.delete_container(s.name)

    click.echo(
        f"\n{'Name':<15} {'PG':<5} {'TSDB':<10} {'IP':<15} {'Port':<6} {'Engine':<8}"
    )
    click.echo("-" * 65)
    for c in containers:
        click.echo(
            f"{c.name:<15} {c.postgres_version:<5} {c.timescaledb_version:<10} {c.bind_ip:<15} {c.port:<6} {c.engine:<8}"
        )


@main.command()
@click.argument("container_name", required=False)
def logs(container_name):
    """Show container logs"""
    if not container_name:
        containers = cli_state.state_tracker.load_containers()
        if not containers:
            click.echo("No containers found.")
            return
        container_name = click.prompt(
            "Container name", type=click.Choice([c.name for c in containers])
        )

    container = next(
        (
            c
            for c in cli_state.state_tracker.load_containers()
            if c.name == container_name
        ),
        None,
    )
    if not container:
        click.echo(f"Container '{container_name}' not found.")
        return

    cli_state.state_tracker.mark_accessed(container_name)
    logs_output = cli_state.docker_client.get_container_logs(container.docker_id)
    click.echo(logs_output)


@main.command()
@click.argument("container_name", required=False)
def remove(container_name):
    """Remove a container"""
    if not container_name:
        containers = cli_state.state_tracker.load_containers()
        if not containers:
            click.echo("No containers found.")
            return
        container_name = click.prompt(
            "Container name", type=click.Choice([c.name for c in containers])
        )

    container = next(
        (
            c
            for c in cli_state.state_tracker.load_containers()
            if c.name == container_name
        ),
        None,
    )
    if not container:
        click.echo(f"Container '{container_name}' not found.")
        return

    if click.confirm(f"Remove container '{container_name}'? This cannot be undone."):
        cli_state.docker_client.remove_container(container.docker_id)
        cli_state.state_tracker.delete_container(container_name)
        click.echo(f"[OK] Container '{container_name}' removed.")


@main.command("removeall")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def removeall(force):
    """Remove all containers"""
    containers = cli_state.state_tracker.load_containers()
    if not containers:
        click.echo("No containers found.")
        return

    click.echo(f"Found {len(containers)} container(s):")
    for c in containers:
        click.echo(
            f"  - {c.name} (PG {c.postgres_version}, TSDB {c.timescaledb_version})"
        )

    if not force and not click.confirm("Remove all containers?"):
        click.echo("Aborted.")
        return

    removed = 0
    failed = 0
    for container in containers:
        try:
            cli_state.docker_client.remove_container(container.docker_id)
            cli_state.state_tracker.delete_container(container.name)
            removed += 1
        except Exception as e:
            click.echo(f"[WARNING] Failed to remove {container.name}: {e}")
            failed += 1

    click.echo(f"[OK] Removed {removed}/{len(containers)} container(s)")
    if failed > 0:
        click.echo(f"[WARNING] {failed} container(s) failed to remove")


@main.command()
@click.argument("container_name", required=False)
def connectstring(container_name):
    """Get psql command for container"""
    if not container_name:
        containers = cli_state.state_tracker.load_containers()
        if not containers:
            click.echo("No containers found.")
            return
        container_name = click.prompt(
            "Container name", type=click.Choice([c.name for c in containers])
        )

    container = next(
        (
            c
            for c in cli_state.state_tracker.load_containers()
            if c.name == container_name
        ),
        None,
    )
    if not container:
        click.echo(f"Container '{container_name}' not found.")
        return

    connection_string = f"postgresql://tsdbadmin:{container.tsdbadmin_password}@{container.bind_ip}:{container.port}/tsdb"
    click.echo(f'psql "{connection_string}"')
    cli_state.state_tracker.mark_accessed(container_name)


@main.command("tablespaces")
@click.argument("container_name", required=False)
@click.option("--names", help="Comma-separated tablespace names")
def create_tablespaces(container_name, names):
    """Create database tablespaces"""
    if not container_name:
        containers = cli_state.state_tracker.load_containers()
        if not containers:
            click.echo("No containers found.")
            return
        container_name = click.prompt(
            "Container name", type=click.Choice([c.name for c in containers])
        )

    container = next(
        (
            c
            for c in cli_state.state_tracker.load_containers()
            if c.name == container_name
        ),
        None,
    )
    if not container:
        click.echo(f"Container '{container_name}' not found.")
        return

    if not names:
        names = click.prompt("Tablespace names (comma-separated)")

    try:
        ts_list = [ts.strip() for ts in names.split(",")]
        click.echo(f"[ACTION] Creating {len(ts_list)} tablespace(s)...")
        results = cli_state.docker_client.create_tablespaces(
            container.docker_id, ts_list
        )
        successful = sum(1 for v in results.values() if v)
        click.echo(f"[OK] Created {successful}/{len(ts_list)} tablespace(s)")
        if successful < len(ts_list):
            failed = [k for k, v in results.items() if not v]
            click.echo(f"   [WARNING]  Failed: {', '.join(failed)}")
        cli_state.state_tracker.mark_accessed(container_name)
    except Exception as e:
        click.echo(f"[ERROR] Tablespace creation failed: {e}")
        raise click.Abort()


@main.command("versionrefresh")
def versionrefresh():
    """Refresh version matrix"""
    click.echo("[REFRESH] Fetching latest TimescaleDB versions...")
    matrix = cli_state.version_manager.refresh()
    versions_found = sum(len(v) for v in matrix.postgres_versions.values())
    pg_versions = len(matrix.postgres_versions)
    click.echo(
        f"[OK] Updated: {pg_versions} PostgreSQL versions, {versions_found} TimescaleDB versions"
    )


@main.command("matrix")
def show_matrix():
    """Display compatibility matrix"""
    cached = cli_state.version_manager.load_from_cache()
    if cached and cli_state.version_manager._is_cache_stale(cached):
        click.echo("[REFRESH] Version cache is outdated, fetching latest...")
    matrix = cli_state.version_manager.get_or_fetch()
    if not matrix.postgres_versions:
        click.echo("[ERROR] No compatibility data available")
        return

    rows = []
    for pg_ver in sorted(matrix.postgres_versions.keys(), key=lambda x: int(x)):
        tsdb_versions = matrix.postgres_versions[pg_ver]
        if tsdb_versions:
            versions_str = ", ".join(tsdb_versions)
            rows.append([f"PostgreSQL {pg_ver}", versions_str])

    if rows:
        click.echo("\nPostgreSQL × TimescaleDB Compatibility Matrix:\n")
        table = tabulate(
            rows,
            headers=["PostgreSQL", "Compatible TimescaleDB Versions"],
            tablefmt="grid",
        )
        click.echo(table)
    else:
        click.echo("[ERROR] No compatibility data available")


def display_connection_info(container: Container) -> None:
    """Display connection information to the user."""
    connection_string = f"postgresql://tsdbadmin:{container.tsdbadmin_password}@{container.bind_ip}:{container.port}/tsdb"
    click.echo(
        f"""
Container '{container.name}' created successfully!

Connect:
  psql "{connection_string}"
"""
    )


def show_interactive_menu() -> None:
    """Show interactive menu when no command specified."""
    choice = click.prompt(
        "What would you like to do?",
        type=click.Choice(["new", "list", "logs", "remove"]),
    )

    if choice == "new":
        ctx = click.get_current_context()
        ctx.invoke(
            new,
            postgres=None,
            timescaledb=None,
            port=None,
            config=None,
            bind_ip=None,
            init=None,
            tablespaces=None,
            force=False,
            rebuild=False,
        )
    elif choice == "list":
        ctx = click.get_current_context()
        ctx.invoke(list_cmd)
    elif choice == "logs":
        ctx = click.get_current_context()
        ctx.invoke(logs, container_name=None)
    elif choice == "remove":
        ctx = click.get_current_context()
        ctx.invoke(remove, container_name=None)


if __name__ == "__main__":
    main()
