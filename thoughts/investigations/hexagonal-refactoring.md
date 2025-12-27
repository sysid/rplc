# Investigation: Hexagonal Architecture Refactoring

## FACTS (Verified)

### Current Data Structures

```
config.py:
  MirrorConfig(source_path, mirror_path, is_directory)
  ParseState (enum for markdown parsing state machine)
  ConfigParser (static class, parses markdown)

mirror.py:
  MirrorManager(config_file, proj_dir, mirror_dir, manage_env)
    - configs: List[MirrorConfig]
    - Methods: swap_in(), swap_out(), delete(), _find_any_sentinel()
  _get_hostname() → str

discovery.py:
  ProjectInfo(proj_dir, mirror_dir, config_file)  ← OVERLAP
  SwapStatus (enum: OUT, IN_THIS, IN_OTHER)
  SwapStatusEntry(rel_path, status, hostname)
```

### Identified Overlap

1. **ProjectInfo ≈ MirrorManager init params**
   - Both hold: `proj_dir`, `mirror_dir`, `config_file`
   - ProjectInfo is a value object; MirrorManager adds behavior

2. **SwapStatus logic duplicated**
   - `MirrorManager._find_any_sentinel()` returns `(sentinel_path, hostname)`
   - `get_swap_status_for_project()` interprets this into `SwapStatus` enum
   - Same logic exists in `swap_in()` and `swap_out()` methods

3. **Hostname handling scattered**
   - `_get_hostname()` in mirror.py
   - Used in discovery.py via import
   - Compared in multiple places

### Current Module Responsibilities

| Module | Responsibility | Layer |
|--------|---------------|-------|
| config.py | Parse markdown config files | Infrastructure |
| mirror.py | File operations + domain logic | Mixed |
| discovery.py | Find projects via .envrc | Infrastructure |
| cli.py | User interface, orchestration | Application |

## THEORIES (Plausible Approaches)

### Theory 1: Full Hexagonal (Ports & Adapters)

```
src/rplc/
├── domain/
│   ├── model.py          # Project, MirrorEntry, SwapState, Hostname
│   └── services.py       # Pure domain logic (no I/O)
├── ports/
│   ├── project_repo.py   # Interface: discover projects
│   ├── config_repo.py    # Interface: load configs
│   └── filesystem.py     # Interface: file operations
├── adapters/
│   ├── envrc_discovery.py
│   ├── markdown_config.py
│   └── local_filesystem.py
└── bin/
    └── cli.py
```

**Pros**: Clean separation, testable, extensible
**Cons**: Significant rewrite, may be over-engineered for this project size

### Theory 2: Minimal Domain Extraction

```
src/rplc/
├── lib/
│   ├── domain.py         # Project, SwapState, Hostname (value objects)
│   ├── config.py         # Unchanged
│   ├── mirror.py         # Uses domain types
│   └── discovery.py      # Uses domain types
└── bin/
    └── cli.py
```

**Pros**: Minimal change, reduces duplication
**Cons**: Still mixes concerns in mirror.py

### Theory 3: Extract SwapState Only

Keep structure, just unify the swap state representation:

```python
# domain.py (new, small)
@dataclass
class SwapState:
    is_swapped_in: bool
    hostname: Optional[str]  # None if swapped out

    @property
    def is_on_this_host(self) -> bool:
        return self.is_swapped_in and self.hostname == get_current_hostname()
```

**Pros**: Smallest change, addresses immediate duplication
**Cons**: Doesn't address Project/ProjectInfo overlap

### Theory 4: Unify Project Representation

```python
# domain.py
@dataclass(frozen=True)
class Project:
    proj_dir: Path
    mirror_dir: Path
    config_file: Path

# MirrorManager takes Project instead of 3 params
class MirrorManager:
    def __init__(self, project: Project, manage_env: bool = True): ...
```

**Pros**: Single source of truth for "what is a project"
**Cons**: Changes MirrorManager API (breaking change internally)

### Theory 5: Do Nothing

The current duplication is minimal and localized. The code works. Tests pass.

**Pros**: No risk, no effort
**Cons**: Duplication remains, may grow over time

## QUESTIONS FOR TOM

Before recommending an approach:

1. **What problem are you solving?**
   - Testability? (mock file system)
   - Code clarity?
   - Future extensibility?
   - All of the above?

2. **How stable is the domain?**
   - Is "Project" well-understood or evolving?
   - Are there other discovery mechanisms planned?
   - Are there other storage backends coming?

3. **What's the acceptable blast radius?**
   - Refactor all files at once?
   - Incremental changes preserving API?

## PRELIMINARY RECOMMENDATION

Given YAGNI and "don't over-abstract":

**Theory 4 (Unify Project Representation)** + **Theory 3 (Extract SwapState)**

This gives:
- Single `Project` dataclass used everywhere
- Single `SwapState` representation
- No new interfaces/ports/adapters
- Minimal structural change
- Preserves existing test structure

```
src/rplc/lib/
├── domain.py    # NEW: Project, SwapState
├── config.py    # Unchanged
├── mirror.py    # Use Project, expose get_swap_state()
└── discovery.py # Use Project, delete ProjectInfo
```

Estimated scope: ~200 lines changed, 0 new files of significant size.

---

*Investigation date: 2025-12-27*
