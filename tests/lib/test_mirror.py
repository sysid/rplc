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
