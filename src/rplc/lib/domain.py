# src/rplc/lib/domain.py
"""Domain model for rplc.

This module contains the core domain types that represent the fundamental
concepts in rplc: projects, swap state, and hostname identity.
"""
import socket
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


def get_hostname() -> str:
    """Get short hostname for the current machine.

    Used for sentinel file naming to track which host has files swapped in.
    Returns lowercase short hostname (before first dot in FQDN).
    """
    return socket.gethostname().split('.')[0].lower()


@dataclass(frozen=True)
class Project:
    """A project managed by rplc.

    Represents the fundamental triple that defines an rplc-managed project:
    where the source files live, where the mirror lives, and which config
    file describes the managed paths.
    """
    proj_dir: Path
    mirror_dir: Path
    config_file: Path


class SwapStatus(Enum):
    """The possible swap states for a managed path."""
    SWAPPED_OUT = "out"
    SWAPPED_IN_THIS_HOST = "in_this"
    SWAPPED_IN_OTHER_HOST = "in_other"


@dataclass(frozen=True)
class SwapState:
    """The swap state of a managed path.

    Represents whether a path is swapped in or out, and if swapped in,
    which host performed the swap.
    """
    status: SwapStatus
    hostname: Optional[str] = None  # Set when status is SWAPPED_IN_*

    @classmethod
    def swapped_out(cls) -> "SwapState":
        """Factory for swapped-out state."""
        return cls(status=SwapStatus.SWAPPED_OUT)

    @classmethod
    def swapped_in(cls, hostname: str) -> "SwapState":
        """Factory for swapped-in state. Determines if this or other host."""
        current = get_hostname()
        if hostname == current:
            return cls(status=SwapStatus.SWAPPED_IN_THIS_HOST, hostname=hostname)
        else:
            return cls(status=SwapStatus.SWAPPED_IN_OTHER_HOST, hostname=hostname)

    @property
    def is_swapped_in(self) -> bool:
        return self.status != SwapStatus.SWAPPED_OUT

    @property
    def is_on_this_host(self) -> bool:
        return self.status == SwapStatus.SWAPPED_IN_THIS_HOST

    @property
    def is_on_other_host(self) -> bool:
        return self.status == SwapStatus.SWAPPED_IN_OTHER_HOST
