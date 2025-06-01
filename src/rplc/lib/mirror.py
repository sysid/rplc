# src/rplc/lib/mirror.py
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from rich import print

from rplc.lib.config import MirrorConfig, ConfigParser

logger = logging.getLogger(__name__)


class MirrorManager:
    """Manage mirroring of files and directories"""
    SENTINEL_SUFFIX = ".rplc_active"
    ORIGINAL_SUFFIX = ".rplc.original"
    MIRROR_BKP_SUFFIX = ".rplc_active.backup"
    ENVRC_FILE = ".envrc"
    RPLC_ENV_VAR = "RPLC_SWAPPED"

    def __init__(
        self,
        config_file: Path,
        *,
        proj_dir: Path,
        mirror_dir: Path,
        manage_env: bool = True
    ) -> None:
        self.config_file = config_file.resolve()
        self.proj_dir = proj_dir.resolve()
        self.mirror_dir = mirror_dir.resolve()
        self.configs = ConfigParser.parse_config(config_file)
        self.manage_env = manage_env
        # Convert paths to absolute with correct bases
        for config in self.configs:
            config.source_path = (self.proj_dir / config.source_path).resolve()
            rel_path = config.source_path.relative_to(self.proj_dir)
            config.mirror_path = (self.mirror_dir / rel_path).resolve()

    def _update_envrc(self, set_var: bool = True) -> None:
        """Update .envrc file with RPLC_SWAPPED variable"""
        if not self.manage_env:
            return

        envrc_path = self.proj_dir / self.ENVRC_FILE
        if not envrc_path.exists():
            return

        content = envrc_path.read_text()
        lines = content.splitlines()

        # Remove existing RPLC_SWAPPED line if present
        lines = [line for line in lines if not line.startswith("export RPLC_SWAPPED=1")]

        # Add new RPLC_SWAPPED line if setting
        if set_var:
            lines.append(f"export {self.RPLC_ENV_VAR}=1")

        # Write back to file
        envrc_path.write_text("\n".join(lines) + "\n")

    def swap_in(self, path: Optional[str] = None) -> None:
        """Swap in mirror versions of files/directories"""
        configs = self._filter_configs(path)
        logger.debug(f"Swapping in: {configs}")

        # Only update envrc if we're actually swapping something
        if configs:
            self._update_envrc(set_var=True)

        for config in configs:
            if not config.mirror_path.exists():
                print(f"[yellow]Warning: Mirror path does not exist: {config.mirror_path}[/yellow]")
                continue

            sentinel = self._get_sentinel_path(config)
            if sentinel.exists():
                print(f"[yellow]Already swapped in: {config.source_path}[/yellow]")
                continue

            # Create sentinel file first to mark the start of the operation
            # self._create_sentinel(config)
            self._copy_path(config.mirror_path, sentinel)

            # Backup original if it exists to .rplc.original
            if config.source_path.exists():
                backup_path = self._get_backup_path(config)
                self._move_path(config.source_path, backup_path)

            # Move mirror content to source
            self._move_path(config.mirror_path, config.source_path)

            print(f"[green]Swapped in: {config.source_path}[/green]")

    def swap_out(self, path: Optional[str] = None) -> None:
        """
        Swap out mirror versions and restore originals.
        If this is the first swap-out (mirror directory empty), moves project files to mirror.
        """
        configs = self._filter_configs(path)
        logger.debug(f"Swapping out: {configs}")

        # Only update envrc if we're actually swapping something
        if configs:
            self._update_envrc(set_var=False)

        for config in configs:
            sentinel = self._get_sentinel_path(config)
            backup_path = self._get_backup_path(config)

            # If no sentinel exists, this path hasn't been swapped in
            if not sentinel.exists():
                # Special case: Initialize mirror directory if target doesn't exist
                if not config.mirror_path.exists() and config.source_path.exists():
                    logger.debug(f"Initializing mirror for: {config.source_path}")
                    self._move_path(config.source_path, config.mirror_path)
                    print(f"[green]Initialized mirror: {config.mirror_path}[/green]")
                else:
                    print(f"[yellow]Already swapped out: {config.source_path}[/yellow]")
                continue

            # Store modified content in mirror
            if config.source_path.exists():
                self._move_path(config.source_path, config.mirror_path)

            # Restore backup to source path if it exists
            if backup_path.exists():
                self._move_path(backup_path, config.source_path)
            else:
                print(f"[yellow]Warning: No backup found for {config.source_path}[/yellow]")

            # Remove sentinel file/directory
            if sentinel.is_dir():
                shutil.rmtree(sentinel)
            else:
                sentinel.unlink()

            print(f"[green]Swapped out: {config.source_path}[/green]")

    def _filter_configs(self, path: Optional[str]) -> List[MirrorConfig]:
        """Filter configs based on specified path"""
        if not path:
            return self.configs
        target_path = (self.proj_dir / Path(path)).resolve()
        return [c for c in self.configs if c.source_path == target_path]

    def _get_backup_path(self, config: MirrorConfig) -> Path:
        """Get backup path for original in mirror directory"""
        rel_path = config.source_path.relative_to(self.proj_dir)
        if config.is_directory:
            backup_path = self.mirror_dir / f"{rel_path}{self.ORIGINAL_SUFFIX}"
        else:
            backup_path = self.mirror_dir / rel_path.parent / f"{rel_path.name}{self.ORIGINAL_SUFFIX}"
        return backup_path.resolve()

    def _get_sentinel_path(self, config: MirrorConfig) -> Path:
        """Get sentinel file path for a config"""
        rel_path = config.source_path.relative_to(self.proj_dir)
        return (self.mirror_dir / f"{rel_path}{self.SENTINEL_SUFFIX}").resolve()

    def _create_sentinel(self, config: MirrorConfig) -> None:
        """Create a sentinel file for a swapped path"""
        sentinel = self._get_sentinel_path(config)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.touch()

    @staticmethod
    def _move_path(src: Path, dst: Path) -> None:
        """Move a path to the destination"""
        logger.debug(f"Moving {src} -> {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()

        try:
            # First try an atomic move
            src.rename(dst)
        except OSError:
            # If atomic move fails (e.g., across devices), fallback to copy and delete
            if src.is_dir():
                shutil.copytree(src, dst)
                shutil.rmtree(src)
            else:
                shutil.copy2(src, dst)
                src.unlink()

    @staticmethod
    def _copy_path(src: Path, dst: Path) -> None:
        """Copy a path to destination, preserving metadata"""
        logger.debug(f"Copying {src} -> {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()

        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
