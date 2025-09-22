# tests/test_mirror.py
import shutil
from pathlib import Path

from rplc.lib.mirror import MirrorManager


def test_mirror_manager_swap_out_with_changes(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test swapping out after making changes"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Store original content
    orig_yml = (proj_dir / "main/resources/application.yml").read_text()
    orig_note = (proj_dir / "scratchdir/note.txt").read_text()
    mirror_yml = (mirror_dir / "main/resources/application.yml").read_text()

    # First swap in
    manager.swap_in()

    # Verify sentinel was created with mirror content
    sentinel_yml = (mirror_dir / f"main/resources/application.yml{manager.SENTINEL_SUFFIX}").read_text()
    assert sentinel_yml == mirror_yml

    # Verify original was backed up
    backup_yml = (mirror_dir / f"main/resources/application.yml{manager.ORIGINAL_SUFFIX}").read_text()
    assert backup_yml == orig_yml

    # Make some changes
    (proj_dir / "main/resources/application.yml").write_text("modified: true")
    (proj_dir / "scratchdir/note.txt").write_text("modified note")

    # Then swap out
    manager.swap_out()

    # Verify modified files were moved to mirror
    assert (mirror_dir / "main/resources/application.yml").read_text() == "modified: true"
    assert (mirror_dir / "scratchdir/note.txt").read_text() == "modified note"

    # Verify original files were restored from backup
    assert (proj_dir / "main/resources/application.yml").read_text() == orig_yml
    assert (proj_dir / "scratchdir/note.txt").read_text() == orig_note

    # Verify sentinel was removed and no backups remain
    assert not (mirror_dir / f"main/resources/application.yml{manager.SENTINEL_SUFFIX}").exists()
    assert not list(mirror_dir.rglob(f"*{manager.SENTINEL_SUFFIX}"))
    assert not list(mirror_dir.rglob(f"*{manager.ORIGINAL_SUFFIX}"))


def test_mirror_manager_initial_swap_out(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test first-time swap-out to initialize mirror directory"""
    proj_dir, mirror_dir = test_project

    # Clear mirror directory
    shutil.rmtree(mirror_dir)
    mirror_dir.mkdir()

    # Store original content for verification
    orig_yml = (proj_dir / "main/resources/application.yml").read_text()
    orig_note = (proj_dir / "scratchdir/note.txt").read_text()

    # Create manager and do initial swap-out
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    manager.swap_out()

    # Verify files were moved to mirror
    assert (mirror_dir / "main/resources/application.yml").read_text() == orig_yml
    assert (mirror_dir / "scratchdir/note.txt").read_text() == orig_note

    # Verify original files are gone (moved to mirror)
    assert not (proj_dir / "main/resources/application.yml").exists()
    assert not (proj_dir / "scratchdir/note.txt").exists()

    # Verify no sentinel files were created
    assert not list(mirror_dir.rglob(f"*{manager.SENTINEL_SUFFIX}"))


def test_mirror_manager_sentinel_handling(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test specific sentinel file handling during swap operations"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Store initial content
    mirror_yml = (mirror_dir / "main/resources/application.yml").read_text()

    # Perform swap-in
    manager.swap_in()

    # Check sentinel content matches original mirror content
    sentinel_path = mirror_dir / f"main/resources/application.yml{manager.SENTINEL_SUFFIX}"
    assert sentinel_path.exists()
    assert sentinel_path.read_text() == mirror_yml

    # Modify file in original location
    modified_content = "modified: true"
    (proj_dir / "main/resources/application.yml").write_text(modified_content)

    # Swap out
    manager.swap_out()

    # Verify:
    # 1. Modified content is in mirror
    assert (mirror_dir / "main/resources/application.yml").read_text() == modified_content
    # 2. Sentinel is removed
    assert not sentinel_path.exists()
    # 3. Original backup was used for restoration
    assert (proj_dir / "main/resources/application.yml").read_text() == "original: true"


def test_mirror_manager_envrc_handling(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test .envrc handling during swap operations"""
    proj_dir, mirror_dir = test_project

    # Create test .envrc
    envrc_path = proj_dir / ".envrc"
    envrc_path.write_text("export OTHER_VAR=123\n")

    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Test swap in
    manager.swap_in()
    assert "export RPLC_SWAPPED=1" in envrc_path.read_text()
    assert "export OTHER_VAR=123" in envrc_path.read_text()

    # Test swap out
    manager.swap_out()
    content = envrc_path.read_text()
    assert "export RPLC_SWAPPED=1" not in content
    assert "export OTHER_VAR=123" in content


def test_mirror_manager_no_env_flag(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test that --no-env flag prevents .envrc modifications"""
    proj_dir, mirror_dir = test_project

    # Create test .envrc
    envrc_path = proj_dir / ".envrc"
    original_content = "export OTHER_VAR=123\n"
    envrc_path.write_text(original_content)

    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir,
        manage_env=False
    )

    # Test swap in
    manager.swap_in()
    assert envrc_path.read_text() == original_content

    # Test swap out
    manager.swap_out()
    assert envrc_path.read_text() == original_content


def test_filter_configs_no_parameters(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test _filter_configs with no parameters returns all configs"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # No filters should return all configs
    filtered = manager._filter_configs()
    assert len(filtered) == len(manager.configs)
    assert filtered == manager.configs


def test_filter_configs_specific_files(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test _filter_configs with specific file list"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Filter for specific file
    filtered = manager._filter_configs(files=["main/resources/application.yml"])
    assert len(filtered) == 1
    assert str(filtered[0].source_path).endswith("main/resources/application.yml")

    # Filter for multiple files
    filtered = manager._filter_configs(files=["main/resources/application.yml", "scratchdir/"])
    assert len(filtered) == 2

    # Filter for non-existent file should show warning but not crash
    filtered = manager._filter_configs(files=["nonexistent.txt"])
    assert len(filtered) == 0


def test_filter_configs_pattern_matching(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test _filter_configs with glob patterns"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Pattern matching for YAML files
    filtered = manager._filter_configs(pattern="*.yml")
    assert len(filtered) == 1
    assert str(filtered[0].source_path).endswith("application.yml")

    # Pattern matching for all files in a directory
    filtered = manager._filter_configs(pattern="main/**/*")
    assert len(filtered) == 2  # should match both .yml and .java files

    # Pattern that matches nothing
    filtered = manager._filter_configs(pattern="*.nonexistent")
    assert len(filtered) == 0


def test_filter_configs_exclude_patterns(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test _filter_configs with exclusion patterns"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Exclude specific patterns
    filtered = manager._filter_configs(exclude=["*.yml"])
    # Should return configs that don't match the exclusion pattern
    assert len(filtered) == 2  # java file and scratchdir should remain

    # Exclude multiple patterns
    filtered = manager._filter_configs(exclude=["*.yml", "*.java"])
    assert len(filtered) == 1  # Should only have scratchdir/

    # Exclude directory patterns
    filtered = manager._filter_configs(exclude=["main/**/*"])
    assert len(filtered) == 1
    assert str(filtered[0].source_path).endswith("scratchdir")


def test_filter_configs_combined_filters(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test _filter_configs with combined files, patterns, and exclusions"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Files + exclusions
    filtered = manager._filter_configs(
        files=["main/resources/application.yml", "main/src/class.java"],
        exclude=["*.java"]
    )
    assert len(filtered) == 1
    assert str(filtered[0].source_path).endswith("application.yml")

    # Pattern + exclusions
    filtered = manager._filter_configs(
        pattern="main/**/*",
        exclude=["*.yml"]
    )
    assert len(filtered) == 1
    assert str(filtered[0].source_path).endswith("class.java")


def test_swap_in_with_specific_files(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test swap_in with specific file filtering"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Swap in only one specific file
    manager.swap_in(files=["main/resources/application.yml"])

    # Check that only the specified file was swapped
    yml_sentinel = mirror_dir / f"main/resources/application.yml{manager.SENTINEL_SUFFIX}"
    java_sentinel = mirror_dir / f"main/src/class.java{manager.SENTINEL_SUFFIX}"
    dir_sentinel = mirror_dir / f"scratchdir{manager.SENTINEL_SUFFIX}"

    assert yml_sentinel.exists()
    assert not java_sentinel.exists()
    assert not dir_sentinel.exists()

    # Verify content was swapped correctly
    assert (proj_dir / "main/resources/application.yml").read_text() == "mirror: true"
    assert (proj_dir / "scratchdir/note.txt").read_text() == "original note"  # directory wasn't touched


def test_swap_out_with_pattern(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test swap_out with pattern filtering"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # First swap in all files
    manager.swap_in()

    # Modify files
    (proj_dir / "main/resources/application.yml").write_text("modified yml")
    (proj_dir / "scratchdir/note.txt").write_text("modified txt")

    # Swap out only YAML files
    manager.swap_out(pattern="*.yml")

    # Check that only YAML file was swapped out
    yml_sentinel = mirror_dir / f"main/resources/application.yml{manager.SENTINEL_SUFFIX}"
    java_sentinel = mirror_dir / f"main/src/class.java{manager.SENTINEL_SUFFIX}"
    dir_sentinel = mirror_dir / f"scratchdir{manager.SENTINEL_SUFFIX}"

    assert not yml_sentinel.exists()  # Should be removed
    assert java_sentinel.exists()      # Should still exist
    assert dir_sentinel.exists()       # Should still exist

    # Verify correct content restoration
    assert (proj_dir / "main/resources/application.yml").read_text() == "original: true"
    assert (proj_dir / "main/src/class.java").read_text() == "mirror java"  # Still swapped
    assert (proj_dir / "scratchdir/note.txt").read_text() == "modified txt"  # Still modified


def test_swap_operations_are_idempotent(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test that multiple swap operations are idempotent"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Store initial state
    initial_yml = (proj_dir / "main/resources/application.yml").read_text()
    initial_txt = (proj_dir / "scratchdir/note.txt").read_text()

    # Swap in multiple times
    manager.swap_in(files=["main/resources/application.yml"])
    first_swap_yml = (proj_dir / "main/resources/application.yml").read_text()

    manager.swap_in(files=["main/resources/application.yml"])
    second_swap_yml = (proj_dir / "main/resources/application.yml").read_text()

    # Should be identical
    assert first_swap_yml == second_swap_yml

    # Swap out multiple times
    manager.swap_out(files=["main/resources/application.yml"])
    first_restore_yml = (proj_dir / "main/resources/application.yml").read_text()

    manager.swap_out(files=["main/resources/application.yml"])
    second_restore_yml = (proj_dir / "main/resources/application.yml").read_text()

    # Should be identical and match initial state
    assert first_restore_yml == second_restore_yml == initial_yml
