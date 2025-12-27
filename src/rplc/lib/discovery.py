# src/rplc/lib/discovery.py
"""Discovery of rplc projects via .envrc files."""
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from rplc.lib.domain import Project, SwapState, SwapStatus, get_hostname

logger = logging.getLogger(__name__)

__all__ = [
    "Project",
    "SwapStatus",
    "SwapStatusEntry",
    "discover_rplc_projects",
    "get_swap_status_for_project",
    "parse_envrc_for_rplc",
]


@dataclass
class SwapStatusEntry:
    """Swap status for a single config entry.

    Combines a path with its swap state for reporting purposes.
    """
    rel_path: str
    status: SwapStatus
    hostname: Optional[str] = None  # Only set for SWAPPED_IN_OTHER_HOST

    @classmethod
    def from_swap_state(cls, rel_path: str, state: SwapState) -> "SwapStatusEntry":
        """Create from a SwapState value object."""
        return cls(rel_path=rel_path, status=state.status, hostname=state.hostname)


def parse_envrc_for_rplc(envrc_path: Path) -> Optional[Dict[str, str]]:
    """Extract RPLC_* variables from .envrc file.

    Parses shell-style variable assignments like:
    - export RPLC_MIRROR_DIR=/path/to/mirror
    - RPLC_CONFIG=sample.md
    - export RPLC_MIRROR_DIR="$HOME/mirror"

    Returns dict with keys: mirror_dir, config (optional)
    Returns None if no RPLC_MIRROR_DIR found.
    """
    if not envrc_path.exists():
        return None

    try:
        content = envrc_path.read_text()
    except (OSError, IOError) as e:
        logger.warning(f"Failed to read {envrc_path}: {e}")
        return None

    result: Dict[str, str] = {}

    # Pattern to match: [export] RPLC_VAR=value or RPLC_VAR="value"
    # Handles: export RPLC_MIRROR_DIR=/path/to/mirror
    #          RPLC_CONFIG=sample.md
    #          export RPLC_MIRROR_DIR="$HOME/mirror"
    pattern = re.compile(
        r'^(?:export\s+)?RPLC_(\w+)=["\']?([^"\'#\n]+)["\']?',
        re.MULTILINE
    )

    for match in pattern.finditer(content):
        var_name = match.group(1).lower()  # MIRROR_DIR -> mirror_dir
        value = match.group(2).strip()

        # Expand environment variables in the value
        value = os.path.expandvars(value)
        value = os.path.expanduser(value)

        result[var_name] = value

    # RPLC_MIRROR_DIR is required
    if "mirror_dir" not in result:
        return None

    return result


def get_swap_status_for_project(
    proj_dir: Path,
    mirror_dir: Path,
    config_file: Path,
    current_hostname: str,
) -> List[SwapStatusEntry]:
    """Check swap status of all entries in a project.

    Uses MirrorManager to load config and check sentinel status.

    Args:
        proj_dir: Project directory
        mirror_dir: Mirror directory
        config_file: Path to config file
        current_hostname: Current machine's hostname

    Returns:
        List of SwapStatusEntry for each config entry
    """
    from rplc.lib.mirror import MirrorManager

    try:
        manager = MirrorManager(
            config_file,
            proj_dir=proj_dir,
            mirror_dir=mirror_dir,
            manage_env=False,  # Don't modify env during status check
        )
    except Exception as e:
        logger.warning(f"Failed to load config for {proj_dir}: {e}")
        return []

    entries: List[SwapStatusEntry] = []

    for config in manager.configs:
        try:
            rel_path = str(config.source_path.relative_to(proj_dir))
        except ValueError:
            rel_path = str(config.source_path)

        sentinel, sentinel_host = manager._find_any_sentinel(config)

        if sentinel is None:
            status = SwapStatus.SWAPPED_OUT
            hostname = None
        elif sentinel_host == current_hostname:
            status = SwapStatus.SWAPPED_IN_THIS_HOST
            hostname = sentinel_host
        else:
            status = SwapStatus.SWAPPED_IN_OTHER_HOST
            hostname = sentinel_host

        entries.append(SwapStatusEntry(
            rel_path=rel_path,
            status=status,
            hostname=hostname,
        ))

    return entries


def discover_rplc_projects(base: Path) -> List[Project]:
    """Find all rplc projects under base by scanning for .envrc files.

    For each .envrc containing RPLC_MIRROR_DIR:
    - proj_dir = .envrc's parent
    - mirror_dir = RPLC_MIRROR_DIR value
    - config_file = RPLC_CONFIG value or default 'sample.md'

    Args:
        base: Base directory to search recursively

    Returns:
        List of discovered Project objects
    """
    base = base.resolve()
    projects: List[Project] = []

    if not base.exists():
        logger.warning(f"Base directory does not exist: {base}")
        return projects

    # Find all .envrc files under base
    for envrc_path in base.rglob(".envrc"):
        logger.debug(f"Checking {envrc_path}")

        rplc_vars = parse_envrc_for_rplc(envrc_path)
        if rplc_vars is None:
            continue

        proj_dir = envrc_path.parent.resolve()

        # Get mirror_dir (required)
        mirror_dir_str = rplc_vars["mirror_dir"]
        if Path(mirror_dir_str).is_absolute():
            mirror_dir = Path(mirror_dir_str).resolve()
        else:
            # Relative path - resolve relative to proj_dir
            mirror_dir = (proj_dir / mirror_dir_str).resolve()

        # Get config file (optional, defaults to sample.md)
        config_name = rplc_vars.get("config", "sample.md")
        if Path(config_name).is_absolute():
            config_file = Path(config_name).resolve()
        else:
            config_file = (proj_dir / config_name).resolve()

        # Validate: config file should exist
        if not config_file.exists():
            logger.debug(f"Skipping {proj_dir}: config file not found: {config_file}")
            continue

        projects.append(Project(
            proj_dir=proj_dir,
            mirror_dir=mirror_dir,
            config_file=config_file,
        ))
        logger.debug(f"Found rplc project: {proj_dir}")

    return projects
