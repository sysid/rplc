# src/rplc/bin/cli.py
import logging
import os
from pathlib import Path
from typing import Optional, Annotated, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from rplc.lib.mirror import MirrorManager
from rplc.lib.domain import get_hostname
from rplc.lib.discovery import discover_rplc_projects, get_swap_status_for_project, SwapStatus

logger = logging.getLogger(__name__)
console = Console()

__version__ = "0.8.0"

app = typer.Typer(help="RPLC - Local Override Exchange for git projects")


def validate_working_directory(proj_dir: Path) -> None:
    """
    Ensure rplc is running from within the project directory.

    Validates that current working directory is either the project directory
    or a subdirectory within it.

    Args:
        proj_dir: The resolved project directory path

    Raises:
        typer.Exit: If current directory is not within project directory
    """
    cwd = Path.cwd().resolve()
    proj_dir_resolved = proj_dir.resolve()

    # Check if cwd is proj_dir or a subdirectory of it
    try:
        cwd.relative_to(proj_dir_resolved)
    except ValueError:
        # cwd is not within proj_dir
        console.print(
            "[red]✗ Error: rplc must be run from within the project directory[/red]"
        )
        console.print(f"  [dim]Current directory:[/dim] {cwd}")
        console.print(f"  [dim]Project directory:[/dim] {proj_dir_resolved}")
        console.print()
        console.print("[yellow]Solutions:[/yellow]")
        console.print(f"  1. cd {proj_dir_resolved}")
        console.print("  2. Set RPLC_PROJ_DIR to your current directory")
        console.print("  3. Use --proj-dir flag with correct path")
        raise typer.Exit(1)


def detect_project_directory() -> Path:
    """
    Detect project directory with validation.

    Uses RPLC_PROJ_DIR env var if set, otherwise uses cwd.
    Validates that the directory looks like a valid project root by
    checking for common project markers.

    Returns:
        Path: The detected project directory

    Raises:
        typer.Exit: If no RPLC_PROJ_DIR is set and cwd has no project markers
    """
    if env_proj_dir := os.getenv("RPLC_PROJ_DIR"):
        return Path(env_proj_dir)

    # No env var set - use cwd but validate it looks like a project
    cwd = Path.cwd()

    # Check for common project markers
    markers = [
        ".git",
        ".envrc",
        "sample.md",
        "README.md",
        "pyproject.toml",
        "package.json",
        ".rplc",
    ]
    has_marker = any((cwd / marker).exists() for marker in markers)

    if not has_marker:
        console.print(
            "[yellow]⚠ Warning: Current directory doesn't appear to be a project root[/yellow]"
        )
        console.print(f"  [dim]Directory:[/dim] {cwd}")
        console.print(f"  [dim]No project markers found:[/dim] {', '.join(markers)}")
        console.print()
        console.print("[yellow]Suggestions:[/yellow]")
        console.print("  1. Set RPLC_PROJ_DIR environment variable")
        console.print("  2. Use --proj-dir flag")
        console.print("  3. Ensure you're in the correct project directory")
        console.print("  4. Create a marker file (e.g., .rplc) in your project root")
        raise typer.Exit(1)

    return cwd


def get_default_proj_dir() -> Path:
    """Get default project directory with validation"""
    return detect_project_directory()


def get_default_mirror_dir() -> Path:
    """Get default mirror directory from environment or default relative path"""
    return Path(os.getenv("RPLC_MIRROR_DIR", "../mirror_proj"))


def get_default_config() -> Path:
    """Get default config file from environment or default name"""
    return Path(os.getenv("RPLC_CONFIG", "sample.md"))


def get_default_no_env() -> bool:
    """Get default no-env setting from environment"""
    return os.getenv("RPLC_NO_ENV", "").lower() in ("1", "true", "yes")


@app.command()
def info(
    proj_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--proj-dir",
            "-p",
            help="Project directory containing original files (env: RPLC_PROJ_DIR)",
        ),
    ] = None,
    mirror_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--mirror-dir",
            "-m",
            help="Directory containing mirrored files (env: RPLC_MIRROR_DIR)",
        ),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Path to config file (env: RPLC_CONFIG)"),
    ] = None,
) -> None:
    """Display configuration information and current swap status"""
    # Use environment variables as defaults if options not provided
    proj_dir = proj_dir or get_default_proj_dir()
    mirror_dir = mirror_dir or get_default_mirror_dir()
    config = config or get_default_config()

    # Validate working directory
    validate_working_directory(proj_dir)

    config_file = config.resolve()

    # Display basic configuration
    console.print(Panel.fit("RPLC Configuration", style="bold blue"))

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Setting", style="cyan", width=20)
    info_table.add_column("Value", style="white")
    info_table.add_column("Source", style="dim", width=12)

    # Show configuration sources
    config_source = "ENV" if os.getenv("RPLC_CONFIG") else "DEFAULT"
    proj_source = "ENV" if os.getenv("RPLC_PROJ_DIR") else "DEFAULT"
    mirror_source = "ENV" if os.getenv("RPLC_MIRROR_DIR") else "DEFAULT"

    info_table.add_row("Config File", str(config_file), config_source)
    info_table.add_row("Project Directory", str(proj_dir.resolve()), proj_source)
    info_table.add_row("Mirror Directory", str(mirror_dir.resolve()), mirror_source)
    info_table.add_row("Config Exists", "✓" if config_file.exists() else "✗", "")
    info_table.add_row("Project Dir Exists", "✓" if proj_dir.exists() else "✗", "")
    info_table.add_row("Mirror Dir Exists", "✓" if mirror_dir.exists() else "✗", "")

    console.print(info_table)
    console.print()

    # Check if config file exists
    if not config_file.exists():
        console.print(f"[red]Error: Config file {config_file} not found[/red]")
        return

    # Create manager to get configuration
    try:
        manager = MirrorManager(
            config_file,
            proj_dir=proj_dir.resolve(),
            mirror_dir=mirror_dir.resolve(),
            manage_env=False,  # Don't modify env for info command
        )
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        return

    # Display configured files/directories
    if not manager.configs:
        console.print("[yellow]No files/directories configured for mirroring[/yellow]")
        return

    console.print(Panel.fit("Configured Files/Directories", style="bold green"))

    files_table = Table()
    files_table.add_column("Type", style="cyan", width=10)
    files_table.add_column("Source Path", style="white")
    files_table.add_column("Mirror Path", style="white")
    files_table.add_column("Status", style="yellow", width=15)

    for cfg in manager.configs:
        # Determine type
        item_type = "Directory" if cfg.is_directory else "File"

        # Check status
        sentinel = manager._get_sentinel_path(cfg)
        if sentinel.exists():
            status = "🔄 Swapped In"
        elif cfg.source_path.exists() and cfg.mirror_path.exists():
            status = "📁 Both Exist"
        elif cfg.source_path.exists():
            status = "📝 Source Only"
        elif cfg.mirror_path.exists():
            status = "🪞 Mirror Only"
        else:
            status = "❌ Missing"

        # Make paths relative to their base directories for display
        try:
            source_rel = cfg.source_path.relative_to(proj_dir.resolve())
        except ValueError:
            source_rel = cfg.source_path

        try:
            mirror_rel = cfg.mirror_path.relative_to(mirror_dir.resolve())
        except ValueError:
            mirror_rel = cfg.mirror_path

        files_table.add_row(item_type, str(source_rel), str(mirror_rel), status)

    console.print(files_table)
    console.print()

    # Check environment status
    envrc_path = proj_dir / ".envrc"
    if envrc_path.exists():
        content = envrc_path.read_text()
        env_status = (
            "🟢 Active" if "export RPLC_SWAPPED=1" in content else "🔴 Inactive"
        )
        console.print(f"Environment Tracking: {env_status}")
    else:
        console.print("Environment Tracking: [dim]No .envrc file[/dim]")

    # Current Status Summary
    console.print()
    swapped_count = sum(
        1 for cfg in manager.configs if manager._get_sentinel_path(cfg).exists()
    )
    total_count = len(manager.configs)

    # Overall status panel
    if swapped_count > 0:
        status_text = f"[bold green]SWAPPED IN[/bold green]\n{swapped_count}/{total_count} files/directories are currently using mirror versions"
        status_style = "green"
    else:
        status_text = f"[bold blue]NORMAL STATE[/bold blue]\nAll files are in their original state (0/{total_count} swapped)"
        status_style = "blue"

    console.print(Panel(status_text, title="Current Status", style=status_style))

    # Detailed swap status if any files are swapped
    if swapped_count > 0:
        console.print("\n[bold]Currently Swapped Files:[/bold]")
        for cfg in manager.configs:
            sentinel = manager._get_sentinel_path(cfg)
            if sentinel.exists():
                try:
                    source_rel = cfg.source_path.relative_to(proj_dir.resolve())
                except ValueError:
                    source_rel = cfg.source_path
                console.print(f"  • {source_rel}")

    # Show environment variable status more prominently
    console.print()
    envrc_path = proj_dir / ".envrc"
    if envrc_path.exists():
        content = envrc_path.read_text()
        if "export RPLC_SWAPPED=1" in content:
            console.print("[green]✓ Environment variable RPLC_SWAPPED is set[/green]")
        else:
            console.print(
                "[yellow]⚠ Environment variable RPLC_SWAPPED is not set[/yellow]"
            )
    else:
        console.print("[dim]ℹ No .envrc file found[/dim]")


@app.command()
def swapin(
    files: Annotated[
        Optional[List[str]], typer.Argument(help="Files/directories to swap in")
    ] = None,
    pattern: Annotated[
        Optional[str],
        typer.Option("--pattern", "-g", help="Glob pattern for file selection"),
    ] = None,
    exclude: Annotated[
        Optional[List[str]], typer.Option("--exclude", "-x", help="Exclude patterns")
    ] = None,
    proj_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--proj-dir",
            "-p",
            help="Project directory containing original files (env: RPLC_PROJ_DIR)",
        ),
    ] = None,
    mirror_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--mirror-dir",
            "-m",
            help="Directory containing mirrored files (env: RPLC_MIRROR_DIR)",
        ),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Path to config file (env: RPLC_CONFIG)"),
    ] = None,
    no_env: Annotated[
        Optional[bool],
        typer.Option("--no-env", help="Disable .envrc management (env: RPLC_NO_ENV)"),
    ] = None,
) -> None:
    """Swap in mirror versions of files/directories"""
    # Use environment variables as defaults if options not provided
    proj_dir = proj_dir or get_default_proj_dir()
    mirror_dir = mirror_dir or get_default_mirror_dir()
    config = config or get_default_config()
    no_env = no_env if no_env is not None else get_default_no_env()

    # Validate working directory
    validate_working_directory(proj_dir)

    config_file = config.resolve()
    if not config_file.exists():
        typer.echo(f"Error: Config file {config_file} not found")
        raise typer.Exit(1)
    manager = MirrorManager(
        config_file,
        proj_dir=proj_dir.resolve(),
        mirror_dir=mirror_dir.resolve(),
        manage_env=not no_env,
    )
    manager.swap_in(files=files, pattern=pattern, exclude=exclude)


@app.command()
def swapout(
    files: Annotated[
        Optional[List[str]], typer.Argument(help="Files/directories to swap out")
    ] = None,
    pattern: Annotated[
        Optional[str],
        typer.Option("--pattern", "-g", help="Glob pattern for file selection"),
    ] = None,
    exclude: Annotated[
        Optional[List[str]], typer.Option("--exclude", "-x", help="Exclude patterns")
    ] = None,
    proj_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--proj-dir",
            "-p",
            help="Project directory containing original files (env: RPLC_PROJ_DIR)",
        ),
    ] = None,
    mirror_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--mirror-dir",
            "-m",
            help="Directory containing mirrored files (env: RPLC_MIRROR_DIR)",
        ),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Path to config file (env: RPLC_CONFIG)"),
    ] = None,
    no_env: Annotated[
        Optional[bool],
        typer.Option("--no-env", help="Disable .envrc management (env: RPLC_NO_ENV)"),
    ] = None,
) -> None:
    """Swap out mirror versions and restore originals"""
    # Use environment variables as defaults if options not provided
    proj_dir = proj_dir or get_default_proj_dir()
    mirror_dir = mirror_dir or get_default_mirror_dir()
    config = config or get_default_config()
    no_env = no_env if no_env is not None else get_default_no_env()

    # Validate working directory
    validate_working_directory(proj_dir)

    config_file = config.resolve()
    if not config_file.exists():
        typer.echo(f"Error: Config file {config_file} not found")
        raise typer.Exit(1)
    manager = MirrorManager(
        config_file,
        proj_dir=proj_dir.resolve(),
        mirror_dir=mirror_dir.resolve(),
        manage_env=not no_env,
    )
    manager.swap_out(files=files, pattern=pattern, exclude=exclude)


@app.command()
def delete(
    files: Annotated[
        Optional[List[str]],
        typer.Argument(help="Files/directories to remove from management"),
    ] = None,
    pattern: Annotated[
        Optional[str],
        typer.Option("--pattern", "-g", help="Glob pattern for file selection"),
    ] = None,
    exclude: Annotated[
        Optional[List[str]], typer.Option("--exclude", "-x", help="Exclude patterns")
    ] = None,
    proj_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--proj-dir",
            "-p",
            help="Project directory containing original files (env: RPLC_PROJ_DIR)",
        ),
    ] = None,
    mirror_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--mirror-dir",
            "-m",
            help="Directory containing mirrored files (env: RPLC_MIRROR_DIR)",
        ),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Path to config file (env: RPLC_CONFIG)"),
    ] = None,
    no_env: Annotated[
        Optional[bool],
        typer.Option("--no-env", help="Disable .envrc management (env: RPLC_NO_ENV)"),
    ] = None,
) -> None:
    """
    Remove files/directories from rplc management.

    This command removes mirror artifacts and configuration entries for the specified
    files/directories. It only works when files are swapped out to avoid data loss.

    Removes:
    - Mirror directory artifacts
    - Backup files (.rplc.original)
    - Configuration file entries

    Use 'rplc swapout' first if files are currently swapped in.
    """
    # Use environment variables as defaults if options not provided
    proj_dir = proj_dir or get_default_proj_dir()
    mirror_dir = mirror_dir or get_default_mirror_dir()
    config = config or get_default_config()
    no_env = no_env if no_env is not None else get_default_no_env()

    # Validate working directory
    validate_working_directory(proj_dir)

    config_file = config.resolve()
    if not config_file.exists():
        typer.echo(f"Error: Config file {config_file} not found")
        raise typer.Exit(1)
    manager = MirrorManager(
        config_file,
        proj_dir=proj_dir.resolve(),
        mirror_dir=mirror_dir.resolve(),
        manage_env=not no_env,
    )
    manager.delete(files=files, pattern=pattern, exclude=exclude)


@app.command("swapout-all")
def swapout_all(
    base: Annotated[
        Path,
        typer.Argument(help="Base directory to search for rplc projects"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be done without doing it"),
    ] = False,
) -> None:
    """
    Swap out all resources across all rplc projects under a directory.

    Discovers rplc projects by scanning for .envrc files containing RPLC_MIRROR_DIR.
    For each project, swaps out resources that are swapped in on the current host.
    Warns about resources swapped in on other hosts.
    """
    base = base.resolve()

    if not base.exists():
        console.print(f"[red]✗ Error: Base directory does not exist: {base}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Scanning for rplc projects under {base}...[/cyan]")
    console.print()

    projects = discover_rplc_projects(base)

    if not projects:
        console.print("[yellow]No rplc projects found.[/yellow]")
        console.print("[dim]Projects must have .envrc with RPLC_MIRROR_DIR set.[/dim]")
        return

    console.print(f"Found [bold]{len(projects)}[/bold] rplc project(s).")
    console.print()

    current_host = get_hostname()

    # Statistics
    total_swapped_out = 0
    total_other_host = 0
    total_already_out = 0
    projects_processed = 0

    for project in projects:
        # Get relative path for display
        try:
            proj_display = project.proj_dir.relative_to(base)
        except ValueError:
            proj_display = project.proj_dir

        # Get swap status for all entries
        entries = get_swap_status_for_project(
            project.proj_dir,
            project.mirror_dir,
            project.config_file,
            current_host,
        )

        if not entries:
            console.print(f"[dim]{proj_display}: no entries or failed to load config[/dim]")
            continue

        # Check if any work to do
        this_host_entries = [e for e in entries if e.status == SwapStatus.SWAPPED_IN_THIS_HOST]
        other_host_entries = [e for e in entries if e.status == SwapStatus.SWAPPED_IN_OTHER_HOST]
        out_entries = [e for e in entries if e.status == SwapStatus.SWAPPED_OUT]

        if not this_host_entries and not other_host_entries:
            console.print(f"[dim]{proj_display}: all {len(out_entries)} entries already swapped out[/dim]")
            total_already_out += len(out_entries)
            continue

        console.print(f"[bold]{proj_display}[/bold]:")

        # Warn about other host entries
        for entry in other_host_entries:
            console.print(f"  [yellow]⚠ Other host '{entry.hostname}': {entry.rel_path}[/yellow]")
            total_other_host += 1

        # Swap out this-host entries
        if this_host_entries:
            if dry_run:
                for entry in this_host_entries:
                    console.print(f"  [cyan]Would swap out: {entry.rel_path}[/cyan]")
                total_swapped_out += len(this_host_entries)
            else:
                # Actually perform the swap-out
                try:
                    manager = MirrorManager(
                        project.config_file,
                        proj_dir=project.proj_dir,
                        mirror_dir=project.mirror_dir,
                        manage_env=True,
                    )
                    # Get the file paths to swap out
                    files_to_swap = [entry.rel_path for entry in this_host_entries]
                    manager.swap_out(files=files_to_swap)
                    total_swapped_out += len(this_host_entries)
                except Exception as e:
                    console.print(f"  [red]✗ Error swapping out: {e}[/red]")

        # Note already-out entries
        if out_entries:
            console.print(f"  [dim]Already out: {len(out_entries)} entries[/dim]")
            total_already_out += len(out_entries)

        projects_processed += 1

    # Summary
    console.print()
    if dry_run:
        console.print("[cyan]Dry run - no changes made[/cyan]")
    console.print("[bold]Summary:[/bold]")
    console.print(f"  {total_swapped_out} resource(s) swapped out")
    console.print(f"  {total_other_host} resource(s) on other host (skipped)")
    console.print(f"  {total_already_out} resource(s) already swapped out")
    console.print(f"  {projects_processed} project(s) processed")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "-v", "--verbose", help="verbosity"),
    version: bool = typer.Option(False, "-V", "--version", help="show version"),
):
    log_fmt = r"%(asctime)-15s %(levelname)-7s %(message)s"
    if verbose:
        logging.basicConfig(
            format=log_fmt, level=logging.DEBUG, datefmt="%m-%d %H:%M:%S"
        )
    else:
        logging.basicConfig(
            format=log_fmt, level=logging.INFO, datefmt="%m-%d %H:%M:%S"
        )
    logging.getLogger("botocore").setLevel(logging.INFO)
    logging.getLogger("boto3").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)

    if ctx.invoked_subcommand is None and version:
        ctx.invoke(print_version)
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())


@app.command("version", help="Show version", hidden=True)
def print_version() -> None:
    typer.echo(f"RPLC version: {__version__}")


if __name__ == "__main__":
    app()
