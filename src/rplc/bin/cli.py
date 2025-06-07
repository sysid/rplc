# src/rplc/bin/cli.py
import logging
from pathlib import Path
from typing import Optional, Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from rplc.lib.mirror import MirrorManager

logger = logging.getLogger(__name__)
console = Console()

__version__ = "0.2.1"

app = typer.Typer(help="RPLC - Local Override Exchange for git projects")


@app.command()
def info(
    proj_dir: Annotated[
        Path,
        typer.Option(
            "--proj-dir", "-p", help="Project directory containing original files"
        ),
    ] = Path.cwd(),
    mirror_dir: Annotated[
        Path,
        typer.Option("--mirror-dir", "-m", help="Directory containing mirrored files"),
    ] = Path("../mirror_proj"),
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config file")
    ] = Path("sample.md"),
) -> None:
    """Display configuration information and current swap status"""
    config_file = config.resolve()

    # Display basic configuration
    console.print(Panel.fit("RPLC Configuration", style="bold blue"))

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Setting", style="cyan", width=20)
    info_table.add_column("Value", style="white")

    info_table.add_row("Config File", str(config_file))
    info_table.add_row("Project Directory", str(proj_dir.resolve()))
    info_table.add_row("Mirror Directory", str(mirror_dir.resolve()))
    info_table.add_row("Config Exists", "✓" if config_file.exists() else "✗")
    info_table.add_row("Project Dir Exists", "✓" if proj_dir.exists() else "✗")
    info_table.add_row("Mirror Dir Exists", "✓" if mirror_dir.exists() else "✗")

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
            manage_env=False  # Don't modify env for info command
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

    for config in manager.configs:
        # Determine type
        item_type = "Directory" if config.is_directory else "File"

        # Check status
        sentinel = manager._get_sentinel_path(config)
        if sentinel.exists():
            status = "🔄 Swapped In"
        elif config.source_path.exists() and config.mirror_path.exists():
            status = "📁 Both Exist"
        elif config.source_path.exists():
            status = "📝 Source Only"
        elif config.mirror_path.exists():
            status = "🪞 Mirror Only"
        else:
            status = "❌ Missing"

        # Make paths relative to their base directories for display
        try:
            source_rel = config.source_path.relative_to(proj_dir.resolve())
        except ValueError:
            source_rel = config.source_path

        try:
            mirror_rel = config.mirror_path.relative_to(mirror_dir.resolve())
        except ValueError:
            mirror_rel = config.mirror_path

        files_table.add_row(
            item_type,
            str(source_rel),
            str(mirror_rel),
            status
        )

    console.print(files_table)
    console.print()

    # Check environment status
    envrc_path = proj_dir / ".envrc"
    if envrc_path.exists():
        content = envrc_path.read_text()
        env_status = "🟢 Active" if "export RPLC_SWAPPED=1" in content else "🔴 Inactive"
        console.print(f"Environment Tracking: {env_status}")
    else:
        console.print("Environment Tracking: [dim]No .envrc file[/dim]")

    # Current Status Summary
    console.print()
    swapped_count = sum(1 for config in manager.configs if manager._get_sentinel_path(config).exists())
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
        for config in manager.configs:
            sentinel = manager._get_sentinel_path(config)
            if sentinel.exists():
                try:
                    source_rel = config.source_path.relative_to(proj_dir.resolve())
                except ValueError:
                    source_rel = config.source_path
                console.print(f"  • {source_rel}")

    # Show environment variable status more prominently
    console.print()
    envrc_path = proj_dir / ".envrc"
    if envrc_path.exists():
        content = envrc_path.read_text()
        if "export RPLC_SWAPPED=1" in content:
            console.print("[green]✓ Environment variable RPLC_SWAPPED is set[/green]")
        else:
            console.print("[yellow]⚠ Environment variable RPLC_SWAPPED is not set[/yellow]")
    else:
        console.print("[dim]ℹ No .envrc file found[/dim]")


@app.command()
def swap_in(
    path: Optional[str] = None,
    proj_dir: Annotated[
        Path,
        typer.Option(
            "--proj-dir", "-p", help="Project directory containing original files"
        ),
    ] = Path.cwd(),
    mirror_dir: Annotated[
        Path,
        typer.Option("--mirror-dir", "-m", help="Directory containing mirrored files"),
    ] = Path("../mirror_proj"),
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config file")
    ] = Path("sample.md"),
    no_env: Annotated[
        bool, typer.Option("--no-env", help="Disable .envrc management")
    ] = False,
) -> None:
    """Swap in mirror versions of files/directories"""
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
    manager.swap_in(path)


@app.command()
def swap_out(
    path: Optional[str] = None,
    proj_dir: Annotated[
        Path,
        typer.Option(
            "--proj-dir", "-p", help="Project directory containing original files"
        ),
    ] = Path.cwd(),
    mirror_dir: Annotated[
        Path,
        typer.Option("--mirror-dir", "-m", help="Directory containing mirrored files"),
    ] = Path("../mirror_proj"),
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config file")
    ] = Path("sample.md"),
    no_env: Annotated[
        bool, typer.Option("--no-env", help="Disable .envrc management")
    ] = False,
) -> None:
    """Swap out mirror versions and restore originals"""
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
    manager.swap_out(path)


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
