# tests/lib/test_config.py
from pathlib import Path
import pytest
from rplc.lib.config import ConfigParser


def test_parse_config_whenValidStructure_thenReturnsConfigs(test_config_file: Path) -> None:
    """Test parsing valid config file with standard structure"""
    configs = ConfigParser.parse_config(test_config_file)
    assert len(configs) == 3
    assert configs[0].source_path == Path("main/resources/application.yml")
    assert configs[0].mirror_path == Path("mirror_proj/main/resources/application.yml")
    assert not configs[0].is_directory
    assert configs[2].source_path == Path("scratchdir")
    assert configs[2].is_directory


def test_parse_config_whenFileNotExists_thenReturnsEmpty(tmp_path: Path) -> None:
    """Test parsing non-existent config file"""
    nonexistent_file = tmp_path / "nonexistent.md"
    configs = ConfigParser.parse_config(nonexistent_file)
    assert len(configs) == 0


def test_parse_config_whenNoRplcConfigSection_thenReturnsEmpty(tmp_path: Path) -> None:
    """Test parsing config file without rplc-config section"""
    config_file = tmp_path / "empty.md"
    config_file.write_text("# Some other content")
    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 0


def test_parse_config_whenCodeBlocksPresent_thenIgnoresCodeBlocks(tmp_path: Path) -> None:
    """Test that parser correctly handles markdown with code blocks"""
    config_file = tmp_path / "test.md"
    content = """# Development
Some text here
```bash
# This is not a markdown heading
echo "just a bash command"
```
## rplc-config
/path/to/file.yml
/another/path/
"""
    config_file.write_text(content)

    configs = ConfigParser.parse_config(config_file)

    assert len(configs) == 2
    assert configs[0].source_path == Path("/path/to/file.yml")
    assert not configs[0].is_directory
    assert configs[1].source_path == Path("/another/path")
    assert configs[1].is_directory


def test_parse_config_whenLevel1DevelopmentOnly_thenIgnoresOtherLevels(tmp_path: Path) -> None:
    """Test that only level 1 # Development sections are recognized"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Some Section

## Development
This should be ignored

## rplc-config
ignored/file.txt

# Development
Valid section

## rplc-config
valid/file.txt

### Development
Also ignored

## rplc-config
also/ignored.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("valid/file.txt")


def test_parse_config_whenLevel2RplcConfigOnly_thenIgnoresOtherLevels(tmp_path: Path) -> None:
    """Test that only level 2 ## rplc-config sections are recognized"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Development

# rplc-config
This is level 1, should be ignored
ignored/file.txt

## rplc-config
This is level 2, should work
valid/file.txt

### rplc-config
This is level 3, should be ignored
also/ignored.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("valid/file.txt")


def test_parse_config_whenRplcConfigNotFirstHeading_thenStillParses(tmp_path: Path) -> None:
    """Test that rplc-config doesn't need to be the first heading under Development"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Development

## Setup Instructions
Some setup content here
More instructions

## Environment Variables
DATABASE_URL=localhost
API_KEY=secret

## rplc-config
main/resources/application.yml
scripts/deploy.sh
config/

## Troubleshooting
Common issues and solutions
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 3
    assert configs[0].source_path == Path("main/resources/application.yml")
    assert configs[1].source_path == Path("scripts/deploy.sh")
    assert configs[2].source_path == Path("config")
    assert configs[2].is_directory


def test_parse_config_whenRplcConfigOutsideDevelopment_thenIgnores(tmp_path: Path) -> None:
    """Test that rplc-config sections outside Development are ignored"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Documentation

## rplc-config
This should be ignored
ignored/file.txt

# Development

## rplc-config
This should work
valid/file.txt

# Deployment

## rplc-config
This should also be ignored
also/ignored.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("valid/file.txt")


def test_parse_config_whenMultipleDevelopmentSections_thenUsesFirst(tmp_path: Path) -> None:
    """Test that only the first level 1 Development section is processed"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Development

## rplc-config
first/file.txt

# Other Section

Some content

# Development

## rplc-config
second/file.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("first/file.txt")


def test_parse_config_whenDevelopmentCaseInsensitive_thenMatches(tmp_path: Path) -> None:
    """Test that Development heading is case-insensitive for 'd'"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# development

## rplc-config
test/file.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("test/file.txt")


def test_parse_config_whenRplcConfigCaseSensitive_thenOnlyExactMatch(tmp_path: Path) -> None:
    """Test that rplc-config heading is case-sensitive"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Development

## RPLC-CONFIG
test/file.txt

## rplc-Config
test/file2.txt

## rplc-config
valid/file.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("valid/file.txt")


def test_parse_config_whenNoDevelopmentSection_thenReturnsEmpty(tmp_path: Path) -> None:
    """Test that no configs are returned without Development section"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Documentation

## rplc-config
ignored/file.txt

# Setup

## rplc-config
also/ignored.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 0


def test_parse_config_whenNoRplcConfigSection_thenReturnsEmpty(tmp_path: Path) -> None:
    """Test that no configs are returned without rplc-config section"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Development

## Setup
Some content

## Environment
More content
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 0


def test_parse_config_whenDevelopmentWithSpacesAndDots_thenMatches(tmp_path: Path) -> None:
    """Test Development heading with various whitespace and dots"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Development...

## rplc-config
test/file.txt
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 1
    assert configs[0].source_path == Path("test/file.txt")


def test_parse_config_whenComplexStructure_thenParsesCorrectly(tmp_path: Path) -> None:
    """Test complex markdown structure with multiple sections and levels"""
    config_file = tmp_path / "test.md"
    config_file.write_text("""# Project Documentation

## Overview
This is a complex project

## Development
This is NOT a level 1 heading

# Development

## Getting Started
Follow these steps

### Prerequisites
- Python 3.12+
- Docker

## rplc-config
src/config/settings.yml
docker/compose.yml
scripts/

### Additional Notes
Some notes here

## Deployment
How to deploy

# Production

## rplc-config
This should be ignored
prod/config.yml
""")

    configs = ConfigParser.parse_config(config_file)
    assert len(configs) == 3
    assert configs[0].source_path == Path("src/config/settings.yml")
    assert configs[1].source_path == Path("docker/compose.yml")
    assert configs[2].source_path == Path("scripts")
    assert configs[2].is_directory
