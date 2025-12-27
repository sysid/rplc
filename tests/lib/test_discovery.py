# tests/lib/test_discovery.py
"""Tests for the discovery module."""
from pathlib import Path

import pytest

from rplc.lib.discovery import (
    discover_rplc_projects,
    get_swap_status_for_project,
    parse_envrc_for_rplc,
    SwapStatus,
)
from rplc.lib.domain import get_hostname


class TestParseEnvrcForRplc:
    """Tests for parse_envrc_for_rplc function."""

    def test_extracts_mirror_dir(self, tmp_path: Path) -> None:
        """Should extract RPLC_MIRROR_DIR from .envrc."""
        envrc = tmp_path / ".envrc"
        envrc.write_text("export RPLC_MIRROR_DIR=/path/to/mirror\n")

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"] == "/path/to/mirror"

    def test_extracts_config(self, tmp_path: Path) -> None:
        """Should extract RPLC_CONFIG from .envrc."""
        envrc = tmp_path / ".envrc"
        envrc.write_text(
            "export RPLC_MIRROR_DIR=/path/to/mirror\n"
            "export RPLC_CONFIG=custom.md\n"
        )

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"] == "/path/to/mirror"
        assert result["config"] == "custom.md"

    def test_returns_none_without_mirror_dir(self, tmp_path: Path) -> None:
        """Should return None if RPLC_MIRROR_DIR is not set."""
        envrc = tmp_path / ".envrc"
        envrc.write_text("export RPLC_CONFIG=sample.md\n")

        result = parse_envrc_for_rplc(envrc)

        assert result is None

    def test_handles_without_export(self, tmp_path: Path) -> None:
        """Should handle variable assignment without 'export' keyword."""
        envrc = tmp_path / ".envrc"
        envrc.write_text("RPLC_MIRROR_DIR=/path/to/mirror\n")

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"] == "/path/to/mirror"

    def test_handles_quoted_values(self, tmp_path: Path) -> None:
        """Should handle quoted values."""
        envrc = tmp_path / ".envrc"
        envrc.write_text('export RPLC_MIRROR_DIR="/path/to/mirror"\n')

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"] == "/path/to/mirror"

    def test_expands_env_vars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should expand environment variables in values."""
        monkeypatch.setenv("MY_BASE", "/my/base")
        envrc = tmp_path / ".envrc"
        envrc.write_text("export RPLC_MIRROR_DIR=$MY_BASE/mirror\n")

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"] == "/my/base/mirror"

    def test_expands_tilde(self, tmp_path: Path) -> None:
        """Should expand tilde to home directory."""
        envrc = tmp_path / ".envrc"
        envrc.write_text("export RPLC_MIRROR_DIR=~/mirror\n")

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"].startswith("/")
        assert "~" not in result["mirror_dir"]

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        """Should return None for non-existent file."""
        envrc = tmp_path / "nonexistent" / ".envrc"

        result = parse_envrc_for_rplc(envrc)

        assert result is None

    def test_handles_mixed_content(self, tmp_path: Path) -> None:
        """Should extract RPLC vars from file with other content."""
        envrc = tmp_path / ".envrc"
        envrc.write_text(
            "# Some comment\n"
            "export PATH=$PATH:/something\n"
            "export RPLC_MIRROR_DIR=/path/to/mirror\n"
            "export OTHER_VAR=value\n"
            "export RPLC_CONFIG=my-config.md\n"
            "dotenv\n"
        )

        result = parse_envrc_for_rplc(envrc)

        assert result is not None
        assert result["mirror_dir"] == "/path/to/mirror"
        assert result["config"] == "my-config.md"


class TestDiscoverRplcProjects:
    """Tests for discover_rplc_projects function."""

    def test_discovers_single_project(self, tmp_path: Path) -> None:
        """Should discover a project with .envrc containing RPLC_MIRROR_DIR."""
        proj_dir = tmp_path / "myproject"
        proj_dir.mkdir()
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        # Create .envrc with RPLC_MIRROR_DIR
        envrc = proj_dir / ".envrc"
        envrc.write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

        # Create default config file
        config = proj_dir / "sample.md"
        config.write_text("# Development\n## rplc-config\ntest.txt\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 1
        assert projects[0].proj_dir == proj_dir
        assert projects[0].mirror_dir == mirror_dir
        assert projects[0].config_file == config

    def test_discovers_multiple_projects(self, tmp_path: Path) -> None:
        """Should discover multiple projects."""
        mirror_dir = tmp_path / "shared_mirror"
        mirror_dir.mkdir()

        for name in ["proj1", "proj2", "proj3"]:
            proj_dir = tmp_path / name
            proj_dir.mkdir()
            (proj_dir / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")
            (proj_dir / "sample.md").write_text("# Development\n## rplc-config\ntest.txt\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 3
        project_names = {p.proj_dir.name for p in projects}
        assert project_names == {"proj1", "proj2", "proj3"}

    def test_skips_projects_without_config(self, tmp_path: Path) -> None:
        """Should skip projects where config file doesn't exist."""
        proj_dir = tmp_path / "myproject"
        proj_dir.mkdir()
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        # Create .envrc but NO config file
        envrc = proj_dir / ".envrc"
        envrc.write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 0

    def test_skips_projects_without_mirror_dir(self, tmp_path: Path) -> None:
        """Should skip projects without RPLC_MIRROR_DIR in .envrc."""
        proj_dir = tmp_path / "myproject"
        proj_dir.mkdir()

        # Create .envrc without RPLC_MIRROR_DIR
        envrc = proj_dir / ".envrc"
        envrc.write_text("export OTHER_VAR=value\n")

        # Create config file
        (proj_dir / "sample.md").write_text("# Development\n## rplc-config\ntest.txt\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 0

    def test_uses_custom_config_from_envrc(self, tmp_path: Path) -> None:
        """Should use RPLC_CONFIG from .envrc if set."""
        proj_dir = tmp_path / "myproject"
        proj_dir.mkdir()
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        envrc = proj_dir / ".envrc"
        envrc.write_text(
            f"export RPLC_MIRROR_DIR={mirror_dir}\n"
            "export RPLC_CONFIG=custom-config.md\n"
        )

        # Create the custom config file
        custom_config = proj_dir / "custom-config.md"
        custom_config.write_text("# Development\n## rplc-config\ntest.txt\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 1
        assert projects[0].config_file == custom_config

    def test_handles_nested_projects(self, tmp_path: Path) -> None:
        """Should discover nested projects."""
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()

        # Create parent project
        parent = tmp_path / "parent"
        parent.mkdir()
        (parent / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}\n")
        (parent / "sample.md").write_text("# Development\n## rplc-config\ntest.txt\n")

        # Create child project
        child = parent / "child"
        child.mkdir()
        (child / ".envrc").write_text(f"export RPLC_MIRROR_DIR={mirror_dir}/child\n")
        (child / "sample.md").write_text("# Development\n## rplc-config\ntest.txt\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 2

    def test_handles_relative_mirror_path(self, tmp_path: Path) -> None:
        """Should resolve relative mirror paths relative to proj_dir."""
        proj_dir = tmp_path / "myproject"
        proj_dir.mkdir()
        mirror_dir = tmp_path / "mirror_proj"
        mirror_dir.mkdir()

        # Use relative path
        envrc = proj_dir / ".envrc"
        envrc.write_text("export RPLC_MIRROR_DIR=../mirror_proj\n")

        (proj_dir / "sample.md").write_text("# Development\n## rplc-config\ntest.txt\n")

        projects = discover_rplc_projects(tmp_path)

        assert len(projects) == 1
        assert projects[0].mirror_dir == mirror_dir

    def test_returns_empty_for_nonexistent_base(self, tmp_path: Path) -> None:
        """Should return empty list for non-existent base directory."""
        nonexistent = tmp_path / "does_not_exist"

        projects = discover_rplc_projects(nonexistent)

        assert projects == []


class TestGetSwapStatusForProject:
    """Tests for get_swap_status_for_project function."""

    def test_returns_swapped_out_status(self, test_project: tuple[Path, Path], test_config_file: Path) -> None:
        """Should return SWAPPED_OUT when no sentinel exists."""
        proj_dir, mirror_dir = test_project
        current_host = get_hostname()

        entries = get_swap_status_for_project(proj_dir, mirror_dir, test_config_file, current_host)

        assert len(entries) > 0
        for entry in entries:
            assert entry.status == SwapStatus.SWAPPED_OUT
            assert entry.hostname is None

    def test_returns_swapped_in_this_host(self, test_project: tuple[Path, Path], test_config_file: Path) -> None:
        """Should return SWAPPED_IN_THIS_HOST when sentinel exists for current host."""
        proj_dir, mirror_dir = test_project
        current_host = get_hostname()

        # Create a sentinel for current host
        sentinel = mirror_dir / f"main/resources/application.yml.{current_host}.rplc_active"
        sentinel.write_text("sentinel content")

        entries = get_swap_status_for_project(proj_dir, mirror_dir, test_config_file, current_host)

        yml_entry = next(e for e in entries if "application.yml" in e.rel_path)
        assert yml_entry.status == SwapStatus.SWAPPED_IN_THIS_HOST
        assert yml_entry.hostname == current_host

    def test_returns_swapped_in_other_host(self, test_project: tuple[Path, Path], test_config_file: Path) -> None:
        """Should return SWAPPED_IN_OTHER_HOST when sentinel exists for different host."""
        proj_dir, mirror_dir = test_project
        current_host = get_hostname()
        other_host = "otherhost"

        # Create a sentinel for different host
        sentinel = mirror_dir / f"main/resources/application.yml.{other_host}.rplc_active"
        sentinel.write_text("sentinel content")

        entries = get_swap_status_for_project(proj_dir, mirror_dir, test_config_file, current_host)

        yml_entry = next(e for e in entries if "application.yml" in e.rel_path)
        assert yml_entry.status == SwapStatus.SWAPPED_IN_OTHER_HOST
        assert yml_entry.hostname == other_host

    def test_handles_mixed_status(self, test_project: tuple[Path, Path], test_config_file: Path) -> None:
        """Should handle different statuses for different entries."""
        proj_dir, mirror_dir = test_project
        current_host = get_hostname()
        other_host = "otherhost"

        # Create sentinel for current host on one file
        sentinel1 = mirror_dir / f"main/resources/application.yml.{current_host}.rplc_active"
        sentinel1.write_text("sentinel content")

        # Create sentinel for other host on another file
        sentinel2 = mirror_dir / f"main/src/class.java.{other_host}.rplc_active"
        sentinel2.write_text("sentinel content")

        entries = get_swap_status_for_project(proj_dir, mirror_dir, test_config_file, current_host)

        yml_entry = next(e for e in entries if "application.yml" in e.rel_path)
        java_entry = next(e for e in entries if "class.java" in e.rel_path)
        dir_entry = next(e for e in entries if "scratchdir" in e.rel_path)

        assert yml_entry.status == SwapStatus.SWAPPED_IN_THIS_HOST
        assert java_entry.status == SwapStatus.SWAPPED_IN_OTHER_HOST
        assert java_entry.hostname == other_host
        assert dir_entry.status == SwapStatus.SWAPPED_OUT

    def test_returns_empty_for_invalid_config(self, tmp_path: Path) -> None:
        """Should return empty list when config file is invalid."""
        proj_dir = tmp_path / "proj"
        proj_dir.mkdir()
        mirror_dir = tmp_path / "mirror"
        mirror_dir.mkdir()
        config_file = tmp_path / "invalid.md"
        config_file.write_text("not a valid rplc config")
        current_host = get_hostname()

        entries = get_swap_status_for_project(proj_dir, mirror_dir, config_file, current_host)

        assert entries == []
