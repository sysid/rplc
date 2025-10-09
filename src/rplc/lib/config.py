# src/rplc/lib/config.py
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List
import re
from enum import Enum


@dataclass
class MirrorConfig:
    """Configuration for mirroring files/directories"""
    source_path: Path
    mirror_path: Path
    is_directory: bool = False


class ParseState(Enum):
    SEARCHING_DEVELOPMENT = "searching_development"
    IN_DEVELOPMENT = "in_development"
    IN_RPLC_CONFIG = "in_rplc_config"
    DONE = "done"


class ConfigParser:
    @staticmethod
    def parse_config(config_file: Path) -> List[MirrorConfig]:
        if not config_file.exists():
            return []

        content = config_file.read_text()

        # Remove content between code fences before processing
        cleaned_content = ConfigParser._remove_code_blocks(content)
        lines = cleaned_content.split('\n')

        state = ParseState.SEARCHING_DEVELOPMENT
        configs: List[MirrorConfig] = []
        found_rplc_config = False  # Track if we've found any rplc-config sections

        for line in lines:
            stripped = line.strip()

            if state == ParseState.SEARCHING_DEVELOPMENT:
                # Look for level-1 heading "# Development" (case insensitive for 'd')
                # Only match exactly level-1, not level-2 or level-3
                if re.match(r'^#\s+[Dd]evelopment', stripped) and not re.match(r'^#{2,}', stripped):
                    state = ParseState.IN_DEVELOPMENT

            elif state == ParseState.IN_DEVELOPMENT:
                # Look for level-2 heading "## rplc-config" (case sensitive)
                if stripped == "## rplc-config":
                    state = ParseState.IN_RPLC_CONFIG
                    found_rplc_config = True
                # Stop if we hit ANY Development heading at any level
                elif re.match(r'^#{1,}\s+[Dd]evelopment', stripped):
                    state = ParseState.DONE
                    break
                # Also stop at level-1 headings if we've already found some rplc-config content
                elif found_rplc_config and re.match(r'^#\s+\w', stripped):
                    state = ParseState.DONE
                    break

            elif state == ParseState.IN_RPLC_CONFIG:
                # Stop if we hit any heading
                if re.match(r'^#{1,}\s+\w', stripped):
                    if stripped == "## rplc-config":
                        # Another rplc-config section, stay in this state
                        continue
                    elif re.match(r'^#{1,}\s+[Dd]evelopment', stripped):
                        # Any Development heading at any level - stop processing
                        state = ParseState.DONE
                        break
                    elif re.match(r'^#\s+\w', stripped):
                        # Level-1 heading, we're done with development
                        state = ParseState.DONE
                        break
                    else:
                        # Level-2+ heading (but not rplc-config or Development), go back to IN_DEVELOPMENT
                        state = ParseState.IN_DEVELOPMENT
                        continue

                # Parse file/directory paths
                if stripped and not stripped.startswith('#'):
                    # Skip description lines (typically start with capital letters and are sentences)
                    if not re.match(r'^[A-Z][a-z].*\s', stripped):
                        # Check if directory (ends with /)
                        is_directory = stripped.endswith('/')
                        # Remove trailing slash for Path creation
                        path_str = stripped.rstrip('/')

                        # Resolve environment variables in the path
                        resolved_path_str = ConfigParser._resolve_env_vars(path_str)

                        path = Path(resolved_path_str)
                        mirror_path = Path("mirror_proj") / path
                        configs.append(MirrorConfig(
                            source_path=path,
                            mirror_path=mirror_path,
                            is_directory=is_directory
                        ))

        return configs

    @staticmethod
    def _resolve_env_vars(path_str: str) -> str:
        """
        Resolve environment variables and user home directory in path strings.
        Supports both $VAR and ${VAR} syntax, plus ~ expansion.
        """
        # First expand user home directory (~)
        expanded = os.path.expanduser(path_str)
        # Then expand environment variables ($VAR and ${VAR})
        resolved = os.path.expandvars(expanded)
        return resolved

    @staticmethod
    def remove_config_entry(config_file: Path, path_to_remove: Path, proj_dir: Path) -> bool:
        """
        Remove a specific path entry from the config file.

        Args:
            config_file: Path to the configuration file
            path_to_remove: Absolute path to remove from configuration
            proj_dir: Project directory for path resolution

        Returns:
            True if entry was found and removed, False otherwise
        """
        if not config_file.exists():
            return False

        # Convert absolute path to relative path as it appears in config
        try:
            rel_path = path_to_remove.relative_to(proj_dir)
        except ValueError:
            # Path might use environment variables - try to match by string
            rel_path = path_to_remove

        content = config_file.read_text()
        lines = content.splitlines(keepends=True)

        state = ParseState.SEARCHING_DEVELOPMENT
        modified = False
        new_lines = []

        for line in lines:
            stripped = line.strip()
            should_keep = True

            # Track state to only process lines within rplc-config sections
            if state == ParseState.SEARCHING_DEVELOPMENT:
                if re.match(r'^#\s+[Dd]evelopment', stripped) and not re.match(r'^#{2,}', stripped):
                    state = ParseState.IN_DEVELOPMENT

            elif state == ParseState.IN_DEVELOPMENT:
                if stripped == "## rplc-config":
                    state = ParseState.IN_RPLC_CONFIG
                elif re.match(r'^#{1,}\s+[Dd]evelopment', stripped):
                    state = ParseState.DONE
                elif re.match(r'^#\s+\w', stripped):
                    state = ParseState.DONE

            elif state == ParseState.IN_RPLC_CONFIG:
                # Check if we hit a new heading
                if re.match(r'^#{1,}\s+\w', stripped):
                    if stripped == "## rplc-config":
                        pass  # Stay in this state
                    elif re.match(r'^#{1,}\s+[Dd]evelopment', stripped):
                        state = ParseState.DONE
                    elif re.match(r'^#\s+\w', stripped):
                        state = ParseState.DONE
                    else:
                        state = ParseState.IN_DEVELOPMENT

                # Check if this line matches the path to remove
                elif stripped and not stripped.startswith('#'):
                    # Check if it's a description line (skip)
                    if not re.match(r'^[A-Z][a-z].*\s', stripped):
                        # This is a path line - check if it matches
                        is_directory = stripped.endswith('/')
                        path_str = stripped.rstrip('/')

                        # Resolve environment variables for comparison
                        resolved_path_str = ConfigParser._resolve_env_vars(path_str)
                        config_path = Path(resolved_path_str)

                        # Compare paths - handle both relative and absolute
                        matches = False
                        if config_path.is_absolute():
                            matches = (config_path == path_to_remove)
                        else:
                            # Relative path - compare with rel_path
                            matches = (config_path == rel_path)

                        if matches:
                            should_keep = False
                            modified = True
                            from rich import print
                            print(f"  [dim]Removing config entry: {stripped}[/dim]")

            if should_keep:
                new_lines.append(line)

        # Write back the modified content
        if modified:
            config_file.write_text(''.join(new_lines))

        return modified

    @staticmethod
    def _remove_code_blocks(content: str) -> str:
        """Remove content between code fences (```...```) from markdown content"""
        pattern = r"```[^`]*```"
        return re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
