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
            "swapin",
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
            "swapin",
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
            "swapout",
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


def test_cli_info_basic_display(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test info command displays basic configuration"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "info",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "RPLC Configuration" in result.output


def test_cli_swapin_with_specific_files(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test swapin command with specific file arguments"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "swapin",
            "main/resources/application.yml",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Swapped in:" in result.output

    # Verify only the specified file was swapped
    assert (proj_dir / "main/resources/application.yml").read_text() == "mirror: true"
    assert (proj_dir / "scratchdir/note.txt").read_text() == "original note"


def test_cli_swapin_with_pattern(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test swapin command with pattern matching"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "swapin",
            "--pattern",
            "*.yml",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Swapped in:" in result.output

    # Verify only YAML files were swapped
    assert (proj_dir / "main/resources/application.yml").read_text() == "mirror: true"
    assert (proj_dir / "scratchdir/note.txt").read_text() == "original note"


def test_cli_swapin_with_exclude(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test swapin command with exclusion patterns"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "swapin",
            "--exclude",
            "*.yml",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Swapped in:" in result.output

    # Verify only non-YAML files were swapped
    assert (proj_dir / "main/resources/application.yml").read_text() == "original: true"
    # Note: the scratchdir/ is configured as a directory, so individual files aren't directly tracked
    # We should check that the java file was swapped instead
    assert (proj_dir / "main/src/class.java").read_text() == "mirror java"


def test_cli_swapout_with_specific_files(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test swapout command with specific file arguments"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # First swap in all files
    runner.invoke(
        app,
        [
            "swapin",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    # Modify files
    (proj_dir / "main/resources/application.yml").write_text("modified yml")
    (proj_dir / "scratchdir/note.txt").write_text("modified txt")

    # Swap out only one file
    result = runner.invoke(
        app,
        [
            "swapout",
            "main/resources/application.yml",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Swapped out:" in result.output

    # Verify only the specified file was swapped out
    assert (proj_dir / "main/resources/application.yml").read_text() == "original: true"
    assert (proj_dir / "scratchdir/note.txt").read_text() == "modified txt"


def test_cli_multiple_files_argument(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test commands with multiple file arguments"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "swapin",
            "main/resources/application.yml",
            "main/src/class.java",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Swapped in:" in result.output

    # Verify both files were swapped
    assert (proj_dir / "main/resources/application.yml").read_text() == "mirror: true"
    assert (proj_dir / "main/src/class.java").read_text() == "mirror java"


def test_cli_invalid_file_warning(
    test_project: tuple[Path, Path], test_config_file: Path
) -> None:
    """Test that invalid files show warnings but don't crash"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "swapin",
            "nonexistent.txt",
            "--proj-dir",
            str(proj_dir),
            "--mirror-dir",
            str(mirror_dir),
            "--config",
            str(test_config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Warning: No configuration found for: nonexistent.txt" in result.output
