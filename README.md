# rplc

## Local File Swapping for Development

A CLI tool for managing custom file versions in private storage.
Swap files in and out on demand to enable personal configurations without polluting the main repository.


## Features

- **File/Directory Mirroring**: Swap between original and mirror versions of files and directories
- **Configuration-Driven**: Define mirror mappings in Markdown configuration files
- **Environment Variable Support**: Use environment variables in path configurations for flexible setups
- **Environment Configuration**: Configure CLI options via environment variables
- **Environment Integration**: Automatic `.envrc` management with swap state tracking
- **Atomic Operations**: Safe file operations with backup and restore capabilities
- **Selective Operations**: Target specific files or operate on entire configurations

## Installation

```bash
pip install rplc
```

Or for development:

```bash
git clone <repository>
cd rplc
uv sync --dev
uv run rplc --help
```

## Quick Start

1. Create a configuration file (e.g., `rplc-config.md`):

```markdown
# Development

## rplc-config
main/resources/application.yml
main/src/class.java
scratchdir/
$HOME/.config/app/local-settings.yml
${PROJECT_ROOT}/temp/
```

2. Set up mirror directory structure:

```
project/
├── main/resources/application.yml    # Original files
├── main/src/class.java
└── scratchdir/
    └── file.txt

mirror_proj/
├── main/resources/application.yml    # Mirror versions
├── main/src/class.java
└── scratchdir/
    └── file.txt
```

3. Swap in mirror versions:

```bash
rplc swap-in --config rplc-config.md
```

4. Swap back to originals:

```bash
rplc swap-out --config rplc-config.md
```

## Environment Variables

RPLC can be configured using environment variables, which serve as defaults when command-line options are not provided:

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `RPLC_CONFIG` | Path to configuration file | `sample.md` |
| `RPLC_PROJ_DIR` | Project directory path | Current directory |
| `RPLC_MIRROR_DIR` | Mirror directory path | `../mirror_proj` |
| `RPLC_NO_ENV` | Disable .envrc management | `false` |

### Example Environment Setup

```bash
# In your .bashrc, .zshrc, or project .envrc
export RPLC_CONFIG="$HOME/.config/rplc/config.md"
export RPLC_PROJ_DIR="/workspace/myproject"
export RPLC_MIRROR_DIR="/workspace/mirror_myproject"
export RPLC_NO_ENV="false"

# Now you can use rplc without specifying options
rplc swap-in
rplc info
```

## Usage

### Commands

#### `info`
Display configuration information and current swap status.

```bash
rplc info [OPTIONS]
```

Shows:
- Configuration paths and their sources (CLI option vs environment variable)
- Configured files/directories with their current status
- Overall swap state (SWAPPED IN / NORMAL STATE)
- Environment variable status

#### `swap-in`
Replace original files with mirror versions.

```bash
rplc swap-in [OPTIONS] [PATH]
```

**Options:**
- `--proj-dir, -p`: Project directory (env: `RPLC_PROJ_DIR`)
- `--mirror-dir, -m`: Mirror directory (env: `RPLC_MIRROR_DIR`)
- `--config, -c`: Configuration file (env: `RPLC_CONFIG`)
- `--no-env`: Disable `.envrc` management (env: `RPLC_NO_ENV`)

**Examples:**
```bash
# Swap all configured files (using environment variables)
rplc swap-in

# Swap specific file
rplc swap-in main/resources/application.yml

# Override environment with explicit options
rplc swap-in --proj-dir /path/to/project --mirror-dir /path/to/mirror
```

#### `swap-out`
Restore original files and move modified versions to mirror.

```bash
rplc swap-out [OPTIONS] [PATH]
```

Uses same options as `swap-in`.

### Configuration Format

Configuration files use Markdown format with a specific structure:

```markdown
# Development

## rplc-config
path/to/file.txt
path/to/directory/
another/file.yml
$HOME/.config/app/settings.yml
${PROJECT_ROOT}/temp/cache/
```

**Rules:**
- Paths ending with `/` are treated as directories
- Paths are relative to project root (unless using environment variables)
- Code blocks are ignored
- Only content under `# Development` → `## rplc-config` is processed
- Environment variables are resolved using `$VAR` or `${VAR}` syntax
    - Undefined environment variables are left as-is (no error thrown)
    - Tilde (`~`) expands to user's home directory
    - Variables can be combined: `~/${PROJECT}/config`
    - Trailing `/` still indicates directories after expansion


### Environment Integration

RPLC automatically manages the `RPLC_SWAPPED` environment variable in `.envrc` files:

- **swap-in**: Sets `export RPLC_SWAPPED=1`
- **swap-out**: Removes the variable

Disable with `--no-env` flag or `RPLC_NO_ENV=true` environment variable.

## How It Works

### Swap-In Process

1. **Backup Original**: Moves original file to `mirror_dir/path.rplc.original`
2. **Create Sentinel**: Copies mirror content to `mirror_dir/path.rplc_active`
3. **Replace Original**: Moves mirror file to original location
4. **Update Environment**: Sets `RPLC_SWAPPED=1` in `.envrc`

### Swap-Out Process

1. **Store Changes**: Moves modified file from original location to mirror
2. **Restore Original**: Moves backup from `mirror_dir/path.rplc.original` to original location
3. **Cleanup**: Removes sentinel files
4. **Update Environment**: Removes `RPLC_SWAPPED` from `.envrc`

### File Structure During Operation

```
project/
├── file.txt                          # Active file (mirror content during swap-in)
└── .envrc                            # Contains RPLC_SWAPPED=1 during swap-in

mirror_proj/
├── file.txt                          # Modified content after swap-out
├── file.txt.rplc.original             # Backup of original content
└── file.txt.rplc_active               # Sentinel marking active swap
```
### Swap State  Tracking
- implemented through **sentinel files**

## 1. Sentinel Files (`.rplc_active`)
- **Purpose**: Track which files are currently swapped in
- **Location**: Mirror directory with `.rplc_active` suffix
- **Content**: Copy of the original mirror content
- **Check**: `sentinel.exists()` determines swap state
- **Cleanup**: Removed during `swap_out`

## 2. Environment Variable (`RPLC_SWAPPED`)
- **Purpose**: Global state indicator in `.envrc`
- **Value**: `export RPLC_SWAPPED=1` when any files are swapped
- **Management**: Automatically added/removed during operations
- **Usage**: External tools can check this variable

**State Flow:**
```
Normal State:     No sentinel files, no RPLC_SWAPPED
Swapped State:    Sentinel files exist, RPLC_SWAPPED=1
```

## Development

### Setup

```bash
# Install dependencies
uv sync --dev

# Install pre-commit hooks
pre-commit install

# Run tests
make test

# Lint and format
make lint
make format
```

### Project Structure

```
src/rplc/
├── bin/
│   ├── __init__.py
│   └── cli.py              # CLI interface
└── lib/
    ├── __init__.py
    ├── config.py           # Configuration parsing
    └── mirror.py           # Core mirroring logic

tests/
├── bin/
│   └── test_cli.py         # CLI tests
├── lib/
│   ├── test_config.py      # Configuration tests
│   └── test_mirror.py      # Core logic tests
└── conftest.py             # Test fixtures
```

### Testing

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-e2e

# Coverage report
make coverage
```

### Building

```bash
# Build package
make build

# Create release
make bump-patch  # or bump-minor, bump-major
```

## Requirements

- Python 3.12+
- typer>=0.15.1

## License

[License information]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `make lint` and `make test`
5. Submit a pull request
