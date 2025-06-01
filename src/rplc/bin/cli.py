# src/rplc/bin/cli.py
import logging
from pathlib import Path
from typing import Optional, Annotated

import typer

from rplc.lib.mirror import MirrorManager

logger = logging.getLogger(__name__)

__version__ = "0.2.1"

app = typer.Typer(help="RPLC - Local Override Exchange for git projects")


# src/rplc/bin/cli.py
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
    typer.echo(f"Confguard version: {__version__}")


if __name__ == "__main__":
    app()
