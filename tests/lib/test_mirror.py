# tests/test_mirror.py
import shutil
from pathlib import Path

import pytest

from rplc.lib.mirror import MirrorManager, _get_hostname


def _sentinel_suffix() -> str:
    """Get the sentinel suffix for the current host"""
    return f".{_get_hostname()}.rplc_active"


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
    sentinel_yml = (mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}").read_text()
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
    assert not (mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}").exists()
    assert not list(mirror_dir.rglob("*.rplc_active"))
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
    assert not list(mirror_dir.rglob("*.rplc_active"))


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
    sentinel_path = mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}"
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
    yml_sentinel = mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}"
    java_sentinel = mirror_dir / f"main/src/class.java{_sentinel_suffix()}"
    dir_sentinel = mirror_dir / f"scratchdir{_sentinel_suffix()}"

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
    yml_sentinel = mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}"
    java_sentinel = mirror_dir / f"main/src/class.java{_sentinel_suffix()}"
    dir_sentinel = mirror_dir / f"scratchdir{_sentinel_suffix()}"

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


def test_swap_in_already_swapped_shows_correct_message(test_project: tuple[Path, Path], test_config_file: Path, capsys) -> None:
    """Test that swap_in shows 'Already swapped in' when files are already swapped on current host"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # First swap in
    manager.swap_in(files=["main/resources/application.yml"])

    # Clear captured output
    capsys.readouterr()

    # Second swap in should show "Already swapped in"
    manager.swap_in(files=["main/resources/application.yml"])

    captured = capsys.readouterr()
    assert "Already swapped in" in captured.out
    # Should NOT show the misleading "Mirror path does not exist" warning
    assert "Mirror path does not exist" not in captured.out


def test_swap_in_blocked_by_other_host(test_project: tuple[Path, Path], test_config_file: Path, capsys) -> None:
    """Test that swap_in is blocked when files are swapped in on a different host"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Manually create a sentinel file from a "different host"
    other_host = "otherhost"
    fake_sentinel = mirror_dir / f"main/resources/application.yml.{other_host}.rplc_active"
    fake_sentinel.parent.mkdir(parents=True, exist_ok=True)
    fake_sentinel.write_text("fake sentinel content")

    # Remove the mirror file to simulate swapped-in state
    (mirror_dir / "main/resources/application.yml").unlink()

    # Attempt to swap in should be blocked
    manager.swap_in(files=["main/resources/application.yml"])

    captured = capsys.readouterr()
    # Output may have line breaks due to rich text wrapping, so normalize
    output = ' '.join(captured.out.split())
    assert f"swapped in on '{other_host}'" in output
    assert "Swap out there first" in output


def test_delete_when_swapped_out(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test delete operation when files are swapped out (normal happy path)"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Store original content for verification
    orig_yml = (proj_dir / "main/resources/application.yml").read_text()

    # Verify mirror artifacts exist before deletion
    assert (mirror_dir / "main/resources/application.yml").exists()

    # Delete the file
    manager.delete(files=["main/resources/application.yml"])

    # Verify mirror artifact was deleted
    assert not (mirror_dir / "main/resources/application.yml").exists()

    # Verify project file is unchanged
    assert (proj_dir / "main/resources/application.yml").read_text() == orig_yml

    # Verify config file was updated
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" not in config_content
    # Other entries should still be present
    assert "main/src/class.java" in config_content
    assert "scratchdir/" in config_content


def test_delete_fails_when_swapped_in(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test that delete fails with clear error when file is swapped in"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Swap in the file
    manager.swap_in(files=["main/resources/application.yml"])

    # Verify sentinel exists (this is the key indicator)
    sentinel = mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}"
    assert sentinel.exists()

    # When swapped in, mirror file has been moved to source, so backup should exist
    backup_path = mirror_dir / f"main/resources/application.yml{manager.ORIGINAL_SUFFIX}"
    assert backup_path.exists()

    # Attempt to delete should fail with SystemExit
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        manager.delete(files=["main/resources/application.yml"])

    assert exc_info.value.code == 1

    # Verify sentinel and backup still exist (nothing was deleted)
    assert sentinel.exists()
    assert backup_path.exists()

    # Verify config file was NOT modified
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" in config_content


def test_delete_with_patterns(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test delete operation with glob patterns"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Delete all YAML files using pattern
    manager.delete(pattern="*.yml")

    # Verify YAML file was deleted
    assert not (mirror_dir / "main/resources/application.yml").exists()

    # Verify other files still exist
    assert (mirror_dir / "main/src/class.java").exists()
    assert (mirror_dir / "scratchdir/note.txt").exists()

    # Verify config file was updated
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" not in config_content
    assert "main/src/class.java" in config_content
    assert "scratchdir/" in config_content


def test_delete_removes_backup_files(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test that delete removes backup files (.rplc.original) if present"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Swap in to create backup (backup is created when swapping in)
    manager.swap_in(files=["main/resources/application.yml"])

    # Verify backup exists while swapped in
    backup_path = mirror_dir / f"main/resources/application.yml{manager.ORIGINAL_SUFFIX}"
    assert backup_path.exists()

    # Swap out to restore normal state
    manager.swap_out(files=["main/resources/application.yml"])

    # After swap out, backup should be gone (moved back to source)
    # But if we manually create a leftover backup to test deletion
    backup_path.write_text("leftover backup")

    # Delete the file
    manager.delete(files=["main/resources/application.yml"])

    # Verify both mirror and backup were deleted
    assert not (mirror_dir / "main/resources/application.yml").exists()
    assert not backup_path.exists()


def test_delete_partial_artifacts(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test delete when only some artifacts exist"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Manually delete mirror file to simulate partial state
    (mirror_dir / "main/resources/application.yml").unlink()

    # Delete should still work and clean up config
    manager.delete(files=["main/resources/application.yml"])

    # Verify config file was updated
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" not in config_content


def test_delete_nonexistent_path(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test delete with path that doesn't exist in config"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Attempt to delete non-existent path - should not crash
    manager.delete(files=["nonexistent/file.txt"])

    # Verify config file unchanged
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" in config_content
    assert "main/src/class.java" in config_content


def test_delete_directory(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test delete operation on a directory"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Verify directory exists
    assert (mirror_dir / "scratchdir").exists()
    assert (mirror_dir / "scratchdir/note.txt").exists()

    # Delete the directory
    manager.delete(files=["scratchdir/"])

    # Verify directory was deleted
    assert not (mirror_dir / "scratchdir").exists()
    assert not (mirror_dir / "scratchdir/note.txt").exists()

    # Verify config file was updated
    config_content = test_config_file.read_text()
    assert "scratchdir/" not in config_content


def test_delete_multiple_files(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test deleting multiple files at once"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Delete multiple files
    manager.delete(files=["main/resources/application.yml", "main/src/class.java"])

    # Verify both were deleted
    assert not (mirror_dir / "main/resources/application.yml").exists()
    assert not (mirror_dir / "main/src/class.java").exists()

    # Verify directory still exists
    assert (mirror_dir / "scratchdir/note.txt").exists()

    # Verify config file was updated
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" not in config_content
    assert "main/src/class.java" not in config_content
    assert "scratchdir/" in config_content


def test_delete_partial_swap_fails(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test that delete fails if any of the targeted files are swapped in"""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Swap in one file but not the other
    manager.swap_in(files=["main/resources/application.yml"])

    # Verify swap state: swapped file has sentinel, non-swapped has mirror
    sentinel_yml = mirror_dir / f"main/resources/application.yml{_sentinel_suffix()}"
    assert sentinel_yml.exists()
    assert (mirror_dir / "main/src/class.java").exists()  # Not swapped, mirror exists

    # Try to delete both - should fail because one is swapped in
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        manager.delete(files=["main/resources/application.yml", "main/src/class.java"])

    assert exc_info.value.code == 1

    # Verify nothing was deleted - sentinel and non-swapped mirror still exist
    assert sentinel_yml.exists()
    assert (mirror_dir / "main/src/class.java").exists()

    # Verify config unchanged
    config_content = test_config_file.read_text()
    assert "main/resources/application.yml" in config_content
    assert "main/src/class.java" in config_content


# ==============================================================================
# .gitignore neutralization tests
# ==============================================================================


def test_gitignore_neutralization_in_directories(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test .gitignore neutralization for directories: swap-out, swap-in, nested files."""
    proj_dir, mirror_dir = test_project
    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Swap in, then add nested .gitignore files
    manager.swap_in(files=["scratchdir/"])
    (proj_dir / "scratchdir/subdir").mkdir()
    (proj_dir / "scratchdir/.gitignore").write_text("*.tmp\n")
    (proj_dir / "scratchdir/subdir/.gitignore").write_text("*.log\n")

    # Swap out - all .gitignore files should be neutralized
    manager.swap_out(files=["scratchdir/"])
    assert not (mirror_dir / "scratchdir/.gitignore").exists()
    assert not (mirror_dir / "scratchdir/subdir/.gitignore").exists()
    assert (mirror_dir / "scratchdir/.gitignore.rplc-disabled").read_text() == "*.tmp\n"
    assert (mirror_dir / "scratchdir/subdir/.gitignore.rplc-disabled").read_text() == "*.log\n"

    # Swap in - all .gitignore files should be restored
    manager.swap_in(files=["scratchdir/"])
    assert (proj_dir / "scratchdir/.gitignore").read_text() == "*.tmp\n"
    assert (proj_dir / "scratchdir/subdir/.gitignore").read_text() == "*.log\n"


def test_standalone_gitignore_full_cycle(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test standalone .gitignore: initial swap-out, swap-in, modify, swap-out again."""
    proj_dir, mirror_dir = test_project

    # Add standalone .gitignore to config
    config_content = test_config_file.read_text()
    config_content += "config/.gitignore\n"
    test_config_file.write_text(config_content)

    (proj_dir / "config").mkdir(exist_ok=True)
    (proj_dir / "config/.gitignore").write_text("*.log\n")

    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    # Initial swap-out - neutralizes in mirror
    manager.swap_out(files=["config/.gitignore"])
    assert not (mirror_dir / "config/.gitignore").exists()
    assert (mirror_dir / "config/.gitignore.rplc-disabled").read_text() == "*.log\n"
    assert not (proj_dir / "config/.gitignore").exists()

    # Swap in - restores to project
    manager.swap_in(files=["config/.gitignore"])
    assert (proj_dir / "config/.gitignore").read_text() == "*.log\n"
    assert not (mirror_dir / "config/.gitignore.rplc-disabled").exists()

    # Modify and swap out again
    (proj_dir / "config/.gitignore").write_text("*.log\n*.tmp\n")
    manager.swap_out(files=["config/.gitignore"])
    assert (mirror_dir / "config/.gitignore.rplc-disabled").read_text() == "*.log\n*.tmp\n"


def test_standalone_gitignore_delete(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test delete operation finds neutralized .gitignore files."""
    proj_dir, mirror_dir = test_project

    config_content = test_config_file.read_text()
    config_content += "config/.gitignore\n"
    test_config_file.write_text(config_content)

    (mirror_dir / "config").mkdir(exist_ok=True)
    (mirror_dir / "config/.gitignore.rplc-disabled").write_text("*.log\n")

    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    manager.delete(files=["config/.gitignore"])

    assert not (mirror_dir / "config/.gitignore.rplc-disabled").exists()
    assert not (mirror_dir / "config/.gitignore").exists()


def test_swap_in_rejects_bare_gitignore(test_project: tuple[Path, Path], test_config_file: Path) -> None:
    """Test swap-in fails when bare .gitignore exists in mirror (standalone or in directory)."""
    proj_dir, mirror_dir = test_project

    # Test 1: Bare .gitignore inside a directory
    (mirror_dir / "scratchdir/.gitignore").write_text("*.tmp\n")

    manager = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    with pytest.raises(SystemExit) as exc_info:
        manager.swap_in(files=["scratchdir/"])
    assert exc_info.value.code == 1
    assert (mirror_dir / "scratchdir/.gitignore").exists()  # unchanged

    # Cleanup for test 2
    (mirror_dir / "scratchdir/.gitignore").unlink()

    # Test 2: Standalone bare .gitignore
    config_content = test_config_file.read_text()
    config_content += "config/.gitignore\n"
    test_config_file.write_text(config_content)

    (mirror_dir / "config").mkdir(exist_ok=True)
    (mirror_dir / "config/.gitignore").write_text("*.log\n")

    manager2 = MirrorManager(
        config_file=test_config_file,
        proj_dir=proj_dir,
        mirror_dir=mirror_dir
    )

    with pytest.raises(SystemExit) as exc_info:
        manager2.swap_in(files=["config/.gitignore"])
    assert exc_info.value.code == 1
    assert (mirror_dir / "config/.gitignore").exists()  # unchanged
