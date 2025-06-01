from pathlib import Path
import pytest
from typer.testing import CliRunner
from rplc.bin.cli import app


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "RPLC - Local Override Exchange" in result.output


def test_cli_swap_in(
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path
) -> None:
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "swap-in",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )
    print("\nTest output:", result.output)  # Debug output
    assert result.exit_code == 0
    assert "Swapped in:" in result.output


def test_cli_swap_out(
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path
) -> None:
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # First swap in
    result = runner.invoke(
        app,
        [
            "swap-in",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )
    assert result.exit_code == 0

    # Then swap out
    result = runner.invoke(
        app,
        [
            "swap-out",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )
    print("\nSwap-out output:", result.output)  # Debug output
    assert result.exit_code == 0
    assert "Swapped out:" in result.output
