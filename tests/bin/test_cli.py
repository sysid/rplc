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
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path, monkeypatch
) -> None:
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path, monkeypatch
) -> None:
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test info command displays basic configuration"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test swapin command with specific file arguments"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test swapin command with pattern matching"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test swapin command with exclusion patterns"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test swapout command with specific file arguments"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test commands with multiple file arguments"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test that invalid files show warnings but don't crash"""
    proj_dir, mirror_dir = test_project
    runner = CliRunner()

    # Change to project directory to satisfy working directory validation
    monkeypatch.chdir(proj_dir)

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


def test_validate_working_directory_from_subdirectory(
    test_project: tuple[Path, Path], test_config_file: Path, monkeypatch
) -> None:
    """Test that commands succeed when run from subdirectory within project"""
    from rplc.bin.cli import validate_working_directory

    proj_dir, mirror_dir = test_project

    # Create and change to a subdirectory
    subdir = proj_dir / "main"
    subdir.mkdir(exist_ok=True)
    monkeypatch.chdir(subdir)

    # Should not raise - subdirectory is valid
    validate_working_directory(proj_dir)


def test_validate_working_directory_from_project_root(
    test_project: tuple[Path, Path], monkeypatch
) -> None:
    """Test that commands succeed when run from project root"""
    from rplc.bin.cli import validate_working_directory

    proj_dir, mirror_dir = test_project

    # Change to project directory
    monkeypatch.chdir(proj_dir)

    # Should not raise - project root is valid
    validate_working_directory(proj_dir)


def test_validate_working_directory_fails_from_parent(
    test_project: tuple[Path, Path], monkeypatch, tmp_path
) -> None:
    """Test that validation fails when run from parent directory"""
    import typer
    from rplc.bin.cli import validate_working_directory

    proj_dir, mirror_dir = test_project

    # Change to parent directory
    monkeypatch.chdir(proj_dir.parent)

    # Should raise typer.Exit (which raises click.exceptions.Exit)
    with pytest.raises((typer.Exit, SystemExit)) as exc_info:
        validate_working_directory(proj_dir)

    # Check exit code
    if hasattr(exc_info.value, "exit_code"):
        assert exc_info.value.exit_code == 1
    else:
        assert exc_info.value.code == 1


def test_validate_working_directory_fails_from_unrelated(
    test_project: tuple[Path, Path], monkeypatch, tmp_path
) -> None:
    """Test that validation fails when run from completely unrelated directory"""
    import typer
    from rplc.bin.cli import validate_working_directory

    proj_dir, mirror_dir = test_project

    # Create and change to unrelated directory
    unrelated = tmp_path / "completely_different"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    # Should raise typer.Exit (which raises click.exceptions.Exit)
    with pytest.raises((typer.Exit, SystemExit)) as exc_info:
        validate_working_directory(proj_dir)

    # Check exit code
    if hasattr(exc_info.value, "exit_code"):
        assert exc_info.value.exit_code == 1
    else:
        assert exc_info.value.code == 1


def test_detect_project_directory_with_env_var(monkeypatch, tmp_path) -> None:
    """Test that RPLC_PROJ_DIR env var is used when set"""
    from rplc.bin.cli import detect_project_directory

    test_dir = tmp_path / "my_project"
    test_dir.mkdir()

    monkeypatch.setenv("RPLC_PROJ_DIR", str(test_dir))

    result = detect_project_directory()
    assert result == test_dir


def test_detect_project_directory_without_markers(monkeypatch, tmp_path) -> None:
    """Test that detection fails when cwd has no project markers and no env var"""
    import typer
    from rplc.bin.cli import detect_project_directory

    # Create directory with no markers
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    # Ensure no env var is set
    monkeypatch.delenv("RPLC_PROJ_DIR", raising=False)

    # Should raise typer.Exit (which raises click.exceptions.Exit)
    with pytest.raises((typer.Exit, SystemExit)) as exc_info:
        detect_project_directory()

    # Check exit code
    if hasattr(exc_info.value, "exit_code"):
        assert exc_info.value.exit_code == 1
    else:
        assert exc_info.value.code == 1


def test_detect_project_directory_with_git_marker(monkeypatch, tmp_path) -> None:
    """Test that detection succeeds with .git marker"""
    from rplc.bin.cli import detect_project_directory

    # Create directory with .git marker
    proj = tmp_path / "with_git"
    proj.mkdir()
    (proj / ".git").mkdir()
    monkeypatch.chdir(proj)

    # Ensure no env var is set
    monkeypatch.delenv("RPLC_PROJ_DIR", raising=False)

    # Should succeed
    result = detect_project_directory()
    assert result == proj


def test_detect_project_directory_with_rplc_marker(monkeypatch, tmp_path) -> None:
    """Test that detection succeeds with .rplc marker"""
    from rplc.bin.cli import detect_project_directory

    # Create directory with .rplc marker
    proj = tmp_path / "with_rplc"
    proj.mkdir()
    (proj / ".rplc").touch()
    monkeypatch.chdir(proj)

    # Ensure no env var is set
    monkeypatch.delenv("RPLC_PROJ_DIR", raising=False)

    # Should succeed
    result = detect_project_directory()
    assert result == proj


# =============================================================================
# Tests for swapout-all command
# =============================================================================


def test_swapout_all_no_projects(tmp_path: Path) -> None:
    """Test swapout-all with no rplc projects found"""
    runner = CliRunner()
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = runner.invoke(app, ["swapout-all", str(empty_dir)])

    assert result.exit_code == 0
    assert "No rplc projects found" in result.output


def test_swapout_all_nonexistent_directory(tmp_path: Path) -> None:
    """Test swapout-all with non-existent base directory"""
    runner = CliRunner()
    nonexistent = tmp_path / "does_not_exist"

    result = runner.invoke(app, ["swapout-all", str(nonexistent)])

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_swapout_all_single_project_all_swapped_out(tmp_path: Path) -> None:
    """Test swapout-all when all files are already swapped out"""
    runner = CliRunner()

    # Create project structure
    proj_dir = tmp_path / "myproject"
    proj_dir.mkdir()
    mirror_dir = tmp_path / "mirror"
    mirror_dir.mkdir()

    # Create .envrc with RPLC_MIRROR_DIR
    (proj_dir / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

    # Create config file
    (proj_dir / "sample.md").write_text("# Development\n## rplc-config\ntest.txt\n")

    # Create mirror file (no sentinel = swapped out)
    (mirror_dir / "test.txt").write_text("mirror content")

    result = runner.invoke(app, ["swapout-all", str(tmp_path)])

    assert result.exit_code == 0
    assert "already swapped out" in result.output


def test_swapout_all_swaps_out_this_host(
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path, monkeypatch
) -> None:
    """Test swapout-all swaps out files that are swapped in on current host"""
    from rplc.lib.mirror import MirrorManager
    from rplc.lib.domain import get_hostname

    runner = CliRunner()
    proj_dir, mirror_dir = test_project

    # Create .envrc pointing to mirror
    (proj_dir / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

    # Copy config to project dir
    (proj_dir / "sample.md").write_text(test_config_file.read_text())

    # Swap in files first
    monkeypatch.chdir(proj_dir)
    manager = MirrorManager(
        proj_dir / "sample.md",
        proj_dir=proj_dir,
        mirror_dir=mirror_dir,
        manage_env=False,
    )
    manager.swap_in()

    # Verify files are swapped in
    hostname = get_hostname()
    sentinel = mirror_dir / f"main/resources/application.yml.{hostname}.rplc_active"
    assert sentinel.exists()

    # Now run swapout-all
    result = runner.invoke(app, ["swapout-all", str(tmp_path / "test_root")])

    print("Output:", result.output)
    assert result.exit_code == 0
    assert "Swapped out" in result.output

    # Verify sentinel is gone
    assert not sentinel.exists()


def test_swapout_all_warns_about_other_host(
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path
) -> None:
    """Test swapout-all warns about files swapped in on other hosts"""
    runner = CliRunner()
    proj_dir, mirror_dir = test_project

    # Create .envrc pointing to mirror
    (proj_dir / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

    # Copy config to project dir
    (proj_dir / "sample.md").write_text(test_config_file.read_text())

    # Create sentinel for different host
    other_host = "otherhost"
    sentinel = mirror_dir / f"main/resources/application.yml.{other_host}.rplc_active"
    sentinel.write_text("sentinel content")

    # Run swapout-all
    result = runner.invoke(app, ["swapout-all", str(tmp_path / "test_root")])

    print("Output:", result.output)
    assert result.exit_code == 0
    assert f"Other host '{other_host}'" in result.output
    assert "on other host" in result.output

    # Verify sentinel still exists (wasn't touched)
    assert sentinel.exists()


def test_swapout_all_dry_run(
    test_project: tuple[Path, Path], test_config_file: Path, tmp_path: Path, monkeypatch
) -> None:
    """Test swapout-all dry-run doesn't actually swap out"""
    from rplc.lib.mirror import MirrorManager
    from rplc.lib.domain import get_hostname

    runner = CliRunner()
    proj_dir, mirror_dir = test_project

    # Create .envrc pointing to mirror
    (proj_dir / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

    # Copy config to project dir
    (proj_dir / "sample.md").write_text(test_config_file.read_text())

    # Swap in files first
    monkeypatch.chdir(proj_dir)
    manager = MirrorManager(
        proj_dir / "sample.md",
        proj_dir=proj_dir,
        mirror_dir=mirror_dir,
        manage_env=False,
    )
    manager.swap_in()

    # Verify files are swapped in
    hostname = get_hostname()
    sentinel = mirror_dir / f"main/resources/application.yml.{hostname}.rplc_active"
    assert sentinel.exists()

    # Run swapout-all with dry-run
    result = runner.invoke(app, ["swapout-all", "--dry-run", str(tmp_path / "test_root")])

    print("Output:", result.output)
    assert result.exit_code == 0
    assert "Would swap out" in result.output
    assert "Dry run" in result.output

    # Verify sentinel still exists (dry-run didn't touch it)
    assert sentinel.exists()


def test_swapout_all_multiple_projects(tmp_path: Path) -> None:
    """Test swapout-all discovers and processes multiple projects"""
    from rplc.lib.mirror import MirrorManager
    from rplc.lib.domain import get_hostname

    runner = CliRunner()
    hostname = get_hostname()

    # Create shared mirror
    mirror_dir = tmp_path / "shared_mirror"
    mirror_dir.mkdir()

    # Create two projects
    for name in ["proj1", "proj2"]:
        proj_dir = tmp_path / name
        proj_dir.mkdir()

        # Create .envrc
        (proj_dir / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

        # Create config
        (proj_dir / "sample.md").write_text(
            f"# Development\n## rplc-config\n{name}_file.txt\n"
        )

        # Create mirror files
        (mirror_dir / f"{name}_file.txt").write_text(f"mirror content for {name}")

        # Create sentinel (swapped in)
        sentinel = mirror_dir / f"{name}_file.txt.{hostname}.rplc_active"
        sentinel.write_text("sentinel")

        # Create source file
        (proj_dir / f"{name}_file.txt").write_text(f"swapped in content for {name}")

        # Create backup
        backup = mirror_dir / f"{name}_file.txt.rplc.original"
        backup.write_text(f"original content for {name}")

    # Run swapout-all
    result = runner.invoke(app, ["swapout-all", str(tmp_path)])

    print("Output:", result.output)
    assert result.exit_code == 0
    assert "Found 2 rplc project(s)" in result.output or "2 project(s) processed" in result.output


def test_swapout_all_help() -> None:
    """Test swapout-all --help shows correct info"""
    runner = CliRunner()
    result = runner.invoke(app, ["swapout-all", "--help"])

    assert result.exit_code == 0
    assert "Swap out all resources" in result.output
    assert "dry-run" in result.output
