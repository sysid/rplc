# src/rplc/lib/mirror.py
import fnmatch
import logging
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from rich import print

from rplc.lib.config import MirrorConfig, ConfigParser
from rplc.lib.domain import get_hostname

logger = logging.getLogger(__name__)



class MirrorManager:
    """Manage mirroring of files and directories"""
    ORIGINAL_SUFFIX = ".rplc.original"
    MIRROR_BKP_SUFFIX = ".rplc_active.backup"
    ENVRC_FILE = ".envrc"
    RPLC_ENV_VAR = "RPLC_SWAPPED"
    GITIGNORE_DISABLED_SUFFIX = ".rplc-disabled"

    @staticmethod
    def _is_gitignore_file(path: Path) -> bool:
        """Check if path refers to a .gitignore file"""
        return path.name == ".gitignore"

    @staticmethod
    def _get_neutralized_path(path: Path) -> Path:
        """Get neutralized form: .gitignore -> .gitignore.rplc-disabled"""
        if path.name == ".gitignore":
            return path.parent / f".gitignore{MirrorManager.GITIGNORE_DISABLED_SUFFIX}"
        return path

    def _get_mirror_physical_path(self, config: MirrorConfig) -> Optional[Path]:
        """Get actual path in mirror. For .gitignore files, returns neutralized path only.

        Returns None if no mirror content exists.
        """
        if config.is_directory:
            return config.mirror_path if config.mirror_path.exists() else None

        if self._is_gitignore_file(config.mirror_path):
            neutralized = self._get_neutralized_path(config.mirror_path)
            return neutralized if neutralized.exists() else None

        return config.mirror_path if config.mirror_path.exists() else None

    def _find_bare_gitignore_in_mirror(self, configs: List[MirrorConfig]) -> List[Path]:
        """Find bare .gitignore files in mirror that should be neutralized.

        Returns list of paths to bare .gitignore files that need to be renamed
        to .gitignore.rplc-disabled before swap-in can proceed.
        """
        bare_gitignores = []
        for config in configs:
            if config.is_directory:
                if config.mirror_path.exists():
                    for gitignore in config.mirror_path.rglob(".gitignore"):
                        bare_gitignores.append(gitignore)
            elif self._is_gitignore_file(config.mirror_path):
                if config.mirror_path.exists():
                    bare_gitignores.append(config.mirror_path)
        return bare_gitignores

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
        self.configs: List[MirrorConfig] = ConfigParser.parse_config(config_file)
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

    def swap_in(self, files: Optional[List[str]] = None, pattern: Optional[str] = None, exclude: Optional[List[str]] = None) -> None:
        """Swap in mirror versions of files/directories"""
        configs = self._filter_configs(files=files, pattern=pattern, exclude=exclude)
        logger.debug(f"Swapping in: {configs}")

        # Safety check: ensure no bare .gitignore files in mirror
        bare_gitignores = self._find_bare_gitignore_in_mirror(configs)
        if bare_gitignores:
            print("[red]✗ Error: Found bare .gitignore files in mirror that need to be neutralized:[/red]")
            for path in bare_gitignores:
                try:
                    rel_path = path.relative_to(self.mirror_dir)
                except ValueError:
                    rel_path = path
                expected = rel_path.parent / f"{rel_path.name}{self.GITIGNORE_DISABLED_SUFFIX}"
                print(f"  [red]• {rel_path}[/red]")
                print(f"    [dim]Rename to: {expected}[/dim]")
            print()
            print("[yellow]Please rename these files manually, then retry swap-in.[/yellow]")
            raise SystemExit(1)

        # Only update envrc if we're actually swapping something
        if configs:
            self._update_envrc(set_var=True)

        current_host = get_hostname()

        for config in configs:
            try:
                rel_path = config.source_path.relative_to(self.proj_dir)
            except ValueError:
                rel_path = config.source_path

            # 1. Check if already swapped in (any host) - MUST check before mirror path
            existing_sentinel, sentinel_host = self._find_any_sentinel(config)
            if existing_sentinel:
                if sentinel_host == current_host:
                    print(f"[yellow]Already swapped in: {rel_path}[/yellow]")
                else:
                    print(f"[red]✗ {rel_path} is swapped in on '{sentinel_host}'. Swap out there first.[/red]")
                continue

            # 2. Now check if mirror path exists
            physical_path = self._get_mirror_physical_path(config)
            if physical_path is None:
                print(f"[yellow]Warning: Mirror path does not exist: {config.mirror_path}[/yellow]")
                continue

            # 3. Create sentinel and proceed with swap
            sentinel = self._get_sentinel_path(config)
            self._copy_path(physical_path, sentinel)

            # Backup original if it exists to .rplc.original
            if config.source_path.exists():
                backup_path = self._get_backup_path(config)
                self._move_path(config.source_path, backup_path)

            # Move mirror content to source
            # For neutralized .gitignore files, move restores the original name
            self._move_path(physical_path, config.source_path)
            if config.is_directory:
                self._enable_gitignore_files(config.source_path)

            print(f"[green]Swapped in: {rel_path}[/green]")

    def swap_out(self, files: Optional[List[str]] = None, pattern: Optional[str] = None, exclude: Optional[List[str]] = None) -> None:
        """
        Swap out mirror versions and restore originals.
        If this is the first swap-out (mirror directory empty), moves project files to mirror.
        """
        configs = self._filter_configs(files=files, pattern=pattern, exclude=exclude)
        logger.debug(f"Swapping out: {configs}")

        # Only update envrc if we're actually swapping something
        if configs:
            self._update_envrc(set_var=False)

        for config in configs:
            try:
                rel_path = config.source_path.relative_to(self.proj_dir)
            except ValueError:
                rel_path = config.source_path

            # Find any existing sentinel (from any host)
            existing_sentinel, sentinel_host = self._find_any_sentinel(config)
            backup_path = self._get_backup_path(config)

            # If no sentinel exists, this path hasn't been swapped in
            if not existing_sentinel:
                # Special case: Initialize mirror directory if target doesn't exist
                if self._get_mirror_physical_path(config) is None and config.source_path.exists():
                    logger.debug(f"Initializing mirror for: {config.source_path}")
                    self._move_path(config.source_path, config.mirror_path)
                    self._disable_gitignore_files(config.mirror_path)
                    print(f"[green]Initialized mirror: {config.mirror_path}[/green]")
                else:
                    print(f"[yellow]Already swapped out: {rel_path}[/yellow]")
                continue

            # Store modified content in mirror
            if config.source_path.exists():
                self._move_path(config.source_path, config.mirror_path)
                self._disable_gitignore_files(config.mirror_path)

            # Restore backup to source path if it exists
            if backup_path.exists():
                self._move_path(backup_path, config.source_path)
            else:
                print(f"[yellow]Warning: No backup (original) found for {rel_path}[/yellow] to bring back.")

            # Remove sentinel file/directory
            if existing_sentinel.is_dir():
                shutil.rmtree(existing_sentinel)
            else:
                existing_sentinel.unlink()

            print(f"[green]Swapped out: {rel_path}[/green]")

        # Report orphaned artifacts (only when no filters applied, i.e. no partial swapout)
        if not any([files, pattern, exclude]):
            orphaned_sentinels, orphaned_backups = self.find_orphaned_artifacts()
            if orphaned_sentinels or orphaned_backups:
                print()
                print("[yellow]Warning: Found orphaned rplc artifacts:[/yellow]")
                for sentinel in orphaned_sentinels:
                    print(f"  [dim]Sentinel: {sentinel}[/dim]")
                for backup in orphaned_backups:
                    print(f"  [dim]Backup: {backup}[/dim]")
                print("[dim]These may be from removed/renamed config entries.[/dim]")
                print("[dim]Delete manually if not needed.[/dim]")

    def delete(self, files: Optional[List[str]] = None, pattern: Optional[str] = None, exclude: Optional[List[str]] = None) -> None:
        """
        Remove paths from rplc management - only works when swapped out.

        Removes:
        - Mirror directory content (mirror_path)
        - Backup files (.rplc.original) if present
        - Configuration entry from config file

        Raises SystemExit if any target is currently swapped in.
        """
        configs = self._filter_configs(files=files, pattern=pattern, exclude=exclude)

        if not configs:
            print("[yellow]No matching files found[/yellow]")
            return

        logger.debug(f"Deleting: {configs}")
        print("[cyan]Checking swap status...[/cyan]")

        # ==============================================================================
        # Safety Check: Ensure Nothing Is Swapped In
        # ==============================================================================
        #
        # We only allow deletion when files are swapped out to avoid edge cases
        # where the user might lose data. If any sentinel file exists, that means
        # the file is currently swapped in and we abort the operation.

        swapped_in_files: List[Tuple[Path, str]] = []
        for config in configs:
            existing_sentinel, sentinel_host = self._find_any_sentinel(config)
            if existing_sentinel:
                swapped_in_files.append((config.source_path, sentinel_host or "unknown"))

        if swapped_in_files:
            print("[red]✗ Error: Cannot delete - the following files are currently swapped in:[/red]")
            current_host = get_hostname()
            for path, host in swapped_in_files:
                try:
                    rel_path = path.relative_to(self.proj_dir)
                except ValueError:
                    rel_path = path
                if host == current_host:
                    print(f"  [red]• {rel_path}[/red]")
                else:
                    print(f"  [red]• {rel_path} (on '{host}')[/red]")
            print("[yellow]Run 'rplc swapout' first to restore original state[/yellow]")
            raise SystemExit(1)

        print("[green]✓ All files are swapped out[/green]")
        print()

        # ==============================================================================
        # Delete Mirror Artifacts
        # ==============================================================================
        #
        # For each configured path, we remove the mirror content and any backup files.
        # We print verbose output so the user knows exactly what's being deleted.

        print("[cyan]Deleting mirror artifacts:[/cyan]")
        deleted_count = 0

        for config in configs:
            # Remove mirror content (accounting for neutralized .gitignore files)
            physical_path = self._get_mirror_physical_path(config)
            if physical_path is not None:
                if physical_path.is_dir():
                    shutil.rmtree(physical_path)
                    print(f"  [dim]Removed directory: {physical_path}[/dim]")
                else:
                    physical_path.unlink()
                    print(f"  [dim]Removed file: {physical_path}[/dim]")
                deleted_count += 1
            else:
                print(f"  [dim]Already removed: {config.mirror_path}[/dim]")

            # Remove backup if it exists
            backup_path = self._get_backup_path(config)
            if backup_path.exists():
                if backup_path.is_dir():
                    shutil.rmtree(backup_path)
                    print(f"  [dim]Removed backup: {backup_path}[/dim]")
                else:
                    backup_path.unlink()
                    print(f"  [dim]Removed backup: {backup_path}[/dim]")

        print(f"[green]✓ Deleted {deleted_count} mirror artifact(s)[/green]")
        print()

        # ==============================================================================
        # Update Configuration File
        # ==============================================================================
        #
        # Remove the path entries from the configuration file so they're no longer
        # managed by rplc. This preserves the markdown structure and other entries.

        print(f"[cyan]Updating configuration file: {self.config_file}[/cyan]")
        removed_count = 0

        for config in configs:
            if ConfigParser.remove_config_entry(self.config_file, config.source_path, self.proj_dir):
                removed_count += 1

        if removed_count > 0:
            print(f"[green]✓ Removed {removed_count} configuration entr{'y' if removed_count == 1 else 'ies'}[/green]")
        else:
            print("[yellow]No configuration entries found to remove[/yellow]")

        print()
        print(f"[green]Successfully removed {len(configs)} file(s) from rplc management[/green]")

    def _filter_configs(self, files: Optional[List[str]] = None, pattern: Optional[str] = None, exclude: Optional[List[str]] = None) -> List[MirrorConfig]:
        """Filter configs based on specified files, patterns, and exclusions"""
        # If no filters specified, return all configs
        if not any([files, pattern, exclude]):
            return self.configs

        filtered_configs = []

        # Start with all configs if no positive filters (files/pattern) are specified
        if not files and not pattern:
            filtered_configs = self.configs.copy()
        else:
            # Apply file-specific filtering
            if files:
                for file_path in files:
                    # Resolve file path relative to project directory
                    if Path(file_path).is_absolute():
                        target_path = Path(file_path).resolve()
                    else:
                        target_path = (self.proj_dir / file_path).resolve()

                    # Find matching configs
                    matching_configs = [c for c in self.configs if c.source_path == target_path]
                    if not matching_configs:
                        print(f"[yellow]Warning: No configuration found for: {file_path}[/yellow]")
                    filtered_configs.extend(matching_configs)

            # Apply pattern-based filtering
            if pattern:
                for config in self.configs:
                    # Get relative path for pattern matching
                    try:
                        rel_path = config.source_path.relative_to(self.proj_dir)
                        if fnmatch.fnmatch(str(rel_path), pattern):
                            if config not in filtered_configs:
                                filtered_configs.append(config)
                    except ValueError:
                        # Skip if path is not relative to project directory
                        pass

        # Apply exclusion filtering
        if exclude:
            excluded_configs = []
            for exclude_pattern in exclude:
                for config in filtered_configs:
                    try:
                        rel_path = config.source_path.relative_to(self.proj_dir)
                        if fnmatch.fnmatch(str(rel_path), exclude_pattern):
                            excluded_configs.append(config)
                    except ValueError:
                        # Skip if path is not relative to project directory
                        pass

            # Remove excluded configs
            filtered_configs = [c for c in filtered_configs if c not in excluded_configs]

        return filtered_configs

    def _get_backup_path(self, config: MirrorConfig) -> Path:
        """Get backup path for original in mirror directory"""
        rel_path = config.source_path.relative_to(self.proj_dir)
        if config.is_directory:
            backup_path = self.mirror_dir / f"{rel_path}{self.ORIGINAL_SUFFIX}"
        else:
            backup_path = self.mirror_dir / rel_path.parent / f"{rel_path.name}{self.ORIGINAL_SUFFIX}"
        return backup_path.resolve()

    def _get_sentinel_path(self, config: MirrorConfig) -> Path:
        """Get sentinel file path for a config (includes hostname)"""
        hostname = get_hostname()
        rel_path = config.source_path.relative_to(self.proj_dir)
        return (self.mirror_dir / f"{rel_path}.{hostname}.rplc_active").resolve()

    def find_orphaned_artifacts(self) -> Tuple[List[Path], List[Path]]:
        """Find orphaned sentinel and backup files in mirror directory.

        After a full swap-out, no sentinel or backup files should remain.
        Any file with these suffixes is orphaned by definition.

        Returns:
            Tuple of (orphaned_sentinels, orphaned_backups)
        """
        orphaned_sentinels = list(self.mirror_dir.rglob("*.rplc_active"))
        orphaned_backups = list(self.mirror_dir.rglob(f"*{self.ORIGINAL_SUFFIX}"))

        return orphaned_sentinels, orphaned_backups

    def _find_any_sentinel(self, config: MirrorConfig) -> Tuple[Optional[Path], Optional[str]]:
        """Find sentinel for any host.

        Returns (sentinel_path, hostname) if a sentinel exists for any host,
        or (None, None) if no sentinel exists.
        """
        rel_path = config.source_path.relative_to(self.proj_dir)
        # Sentinel path: mirror_dir/rel_path.hostname.rplc_active
        # For nested paths like "src/main.py", sentinel is at "mirror_dir/src/main.py.hostname.rplc_active"
        sentinel_dir = (self.mirror_dir / rel_path).parent
        base_name = rel_path.name

        if not sentinel_dir.exists():
            return None, None

        # Pattern: {filename}.{hostname}.rplc_active
        for sentinel in sentinel_dir.glob(f"{base_name}.*.rplc_active"):
            # Extract hostname from: {name}.{hostname}.rplc_active
            parts = sentinel.name.rsplit('.', 2)
            if len(parts) >= 3 and parts[-1] == "rplc_active":
                return sentinel, parts[-2]
        return None, None

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

    @staticmethod
    def _disable_gitignore_files(path: Path) -> None:
        """Rename .gitignore → .gitignore.rplc-disabled.

        For directories: recursively finds and renames all .gitignore files.
        For standalone .gitignore files: renames the file directly.

        Prevents .gitignore files in mirror directories from affecting the
        parent project's git behavior when files are swapped out.
        """
        if path.is_dir():
            for gitignore in path.rglob(".gitignore"):
                disabled = gitignore.parent / f".gitignore{MirrorManager.GITIGNORE_DISABLED_SUFFIX}"
                gitignore.rename(disabled)
                logger.debug(f"Disabled gitignore: {gitignore} → {disabled}")
        elif path.name == ".gitignore" and path.exists():
            disabled = path.parent / f".gitignore{MirrorManager.GITIGNORE_DISABLED_SUFFIX}"
            path.rename(disabled)
            logger.debug(f"Disabled gitignore: {path} → {disabled}")

    @staticmethod
    def _enable_gitignore_files(path: Path) -> None:
        """Rename .gitignore.rplc-disabled → .gitignore.

        For directories: recursively finds and restores all disabled .gitignore files.
        For standalone .gitignore paths: checks if the disabled form exists and restores it.

        Restores .gitignore files when content is swapped back into the
        source project.
        """
        disabled_suffix = MirrorManager.GITIGNORE_DISABLED_SUFFIX
        if path.is_dir():
            for disabled in path.rglob(f".gitignore{disabled_suffix}"):
                gitignore = disabled.parent / ".gitignore"
                disabled.rename(gitignore)
                logger.debug(f"Enabled gitignore: {disabled} → {gitignore}")
        elif path.name == ".gitignore":
            # The path passed is the expected .gitignore path; check if disabled form exists
            disabled = path.parent / f".gitignore{disabled_suffix}"
            if disabled.exists():
                disabled.rename(path)
                logger.debug(f"Enabled gitignore: {disabled} → {path}")
