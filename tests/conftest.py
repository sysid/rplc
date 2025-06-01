# tests/conftest.py
from pathlib import Path
import pytest

@pytest.fixture
def test_project(tmp_path: Path) -> tuple[Path, Path]:
    """Create test project structure with separate project and mirror directories"""
    base_dir = tmp_path / "test_root"
    proj_dir = base_dir / "proj"
    mirror_dir = base_dir / "mirror_proj"

    # Create project directories
    (proj_dir / "main/resources").mkdir(parents=True)
    (proj_dir / "main/src").mkdir(parents=True)
    (proj_dir / "scratchdir").mkdir(parents=True)

    # Create mirror directories
    (mirror_dir / "main/resources").mkdir(parents=True)
    (mirror_dir / "main/src").mkdir(parents=True)
    (mirror_dir / "scratchdir").mkdir(parents=True)

    # Create original files
    (proj_dir / "main/resources/application.yml").write_text("original: true")
    (proj_dir / "main/src/class.java").write_text("original java")
    (proj_dir / "scratchdir/note.txt").write_text("original note")

    # Create mirror files
    (mirror_dir / "main/resources/application.yml").write_text("mirror: true")
    (mirror_dir / "main/src/class.java").write_text("mirror java")
    (mirror_dir / "scratchdir/note.txt").write_text("mirror note")

    return proj_dir, mirror_dir

@pytest.fixture
def test_config_file(tmp_path: Path) -> Path:
    """Create test config file in a temporary location"""
    config_file = tmp_path / "rplc-config.md"
    config_file.write_text("""# development
## rplc-config
main/resources/application.yml
main/src/class.java
scratchdir/
""")
    return config_file
