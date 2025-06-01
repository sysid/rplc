# tests/lib/test_config_env_vars.py
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from rplc.lib.config import ConfigParser, MirrorConfig


class TestConfigEnvVarResolution:
    """Test environment variable resolution in config parsing"""

    def test_resolve_env_vars_simple_syntax(self) -> None:
        """Test resolving environment variables with $VAR syntax"""
        with patch.dict(os.environ, {'HOME': '/home/user', 'PROJECT': '/workspace'}):
            result = ConfigParser._resolve_env_vars('$HOME/config')
            assert result == '/home/user/config'

            result = ConfigParser._resolve_env_vars('$PROJECT/src/main')
            assert result == '/workspace/src/main'

    def test_resolve_env_vars_braced_syntax(self) -> None:
        """Test resolving environment variables with ${VAR} syntax"""
        with patch.dict(os.environ, {'HOME': '/home/user', 'PROJECT_ROOT': '/workspace'}):
            result = ConfigParser._resolve_env_vars('${HOME}/config')
            assert result == '/home/user/config'

            result = ConfigParser._resolve_env_vars('${PROJECT_ROOT}/src/main')
            assert result == '/workspace/src/main'

    def test_resolve_env_vars_mixed_syntax(self) -> None:
        """Test resolving mixed environment variable syntax in one path"""
        with patch.dict(os.environ, {'HOME': '/home/user', 'PROJECT': 'myapp'}):
            result = ConfigParser._resolve_env_vars('$HOME/${PROJECT}/config')
            assert result == '/home/user/myapp/config'

    def test_resolve_env_vars_multiple_vars(self) -> None:
        """Test resolving multiple environment variables in one path"""
        with patch.dict(os.environ, {'USER': 'alice', 'WORKSPACE': '/workspace'}):
            result = ConfigParser._resolve_env_vars('$WORKSPACE/$USER/config')
            assert result == '/workspace/alice/config'

    def test_resolve_env_vars_no_vars(self) -> None:
        """Test path without environment variables remains unchanged"""
        result = ConfigParser._resolve_env_vars('src/main/config')
        assert result == 'src/main/config'

    def test_resolve_env_vars_undefined_simple_leaves_unchanged(self) -> None:
        """Test undefined environment variable with $VAR syntax is left unchanged"""
        with patch.dict(os.environ, {}, clear=True):
            result = ConfigParser._resolve_env_vars('$UNDEFINED_VAR/config')
            assert result == '$UNDEFINED_VAR/config'

    def test_resolve_env_vars_undefined_braced_leaves_unchanged(self) -> None:
        """Test undefined environment variable with ${VAR} syntax is left unchanged"""
        with patch.dict(os.environ, {}, clear=True):
            result = ConfigParser._resolve_env_vars('${UNDEFINED_VAR}/config')
            assert result == '${UNDEFINED_VAR}/config'

    def test_resolve_env_vars_empty_var(self) -> None:
        """Test empty environment variable resolves to empty string"""
        with patch.dict(os.environ, {'EMPTY_VAR': ''}):
            result = ConfigParser._resolve_env_vars('$EMPTY_VAR/config')
            assert result == '/config'

    def test_resolve_env_vars_tilde_expansion(self) -> None:
        """Test tilde (~) expansion for home directory"""
        result = ConfigParser._resolve_env_vars('~/config/app.yml')
        expected = os.path.expanduser('~/config/app.yml')
        assert result == expected

    def test_resolve_env_vars_tilde_and_env_vars(self) -> None:
        """Test combining tilde expansion with environment variables"""
        with patch.dict(os.environ, {'PROJECT': 'myapp'}):
            result = ConfigParser._resolve_env_vars('~/${PROJECT}/config')
            home_dir = os.path.expanduser('~')
            assert result == f'{home_dir}/myapp/config'

    def test_resolve_env_vars_special_characters(self) -> None:
        """Test environment variables with special characters in values"""
        with patch.dict(os.environ, {'SPECIAL_PATH': '/path with spaces/and-dashes'}):
            result = ConfigParser._resolve_env_vars('$SPECIAL_PATH/config')
            assert result == '/path with spaces/and-dashes/config'

    def test_parse_config_with_env_vars_integration(self, tmp_path: Path) -> None:
        """Test full integration of environment variable resolution in config parsing"""
        config_content = """# Development

## rplc-config
$HOME/config/application.yml
${PROJECT_ROOT}/src/main/
$WORKSPACE/temp/file.txt
"""
        config_file = tmp_path / "test-config.md"
        config_file.write_text(config_content)

        with patch.dict(os.environ, {
            'HOME': '/home/user',
            'PROJECT_ROOT': '/workspace/myproject',
            'WORKSPACE': '/workspace'
        }):
            configs = ConfigParser.parse_config(config_file)

        assert len(configs) == 3

        # Check resolved paths
        assert configs[0].source_path == Path('/home/user/config/application.yml')
        assert not configs[0].is_directory

        assert configs[1].source_path == Path('/workspace/myproject/src/main')
        assert configs[1].is_directory

        assert configs[2].source_path == Path('/workspace/temp/file.txt')
        assert not configs[2].is_directory

    def test_parse_config_with_env_vars_error_handling(self, tmp_path: Path) -> None:
        """Test handling when environment variables are not defined (left unchanged)"""
        config_content = """# Development

## rplc-config
$UNDEFINED_VAR/config/application.yml
"""
        config_file = tmp_path / "test-config.md"
        config_file.write_text(config_content)

        with patch.dict(os.environ, {}, clear=True):
            configs = ConfigParser.parse_config(config_file)
            assert len(configs) == 1
            assert str(configs[0].source_path) == '$UNDEFINED_VAR/config/application.yml'

    def test_parse_config_mixed_env_and_regular_paths(self, tmp_path: Path) -> None:
        """Test mixing environment variable paths with regular paths"""
        config_content = """# Development

## rplc-config
$HOME/config/application.yml
src/main/resources/
${PROJECT}/temp/
regular/path/file.txt
"""
        config_file = tmp_path / "test-config.md"
        config_file.write_text(config_content)

        with patch.dict(os.environ, {
            'HOME': '/home/user',
            'PROJECT': '/workspace/myproject'
        }):
            configs = ConfigParser.parse_config(config_file)

        assert len(configs) == 4

        # Environment variable paths
        assert configs[0].source_path == Path('/home/user/config/application.yml')
        assert configs[2].source_path == Path('/workspace/myproject/temp')

        # Regular paths
        assert configs[1].source_path == Path('src/main/resources')
        assert configs[3].source_path == Path('regular/path/file.txt')

    def test_env_var_resolution_preserves_directory_detection(self, tmp_path: Path) -> None:
        """Test that environment variable resolution preserves directory detection"""
        config_content = """# Development

## rplc-config
$HOME/config/
${PROJECT}/src/main/resources/app.yml
"""
        config_file = tmp_path / "test-config.md"
        config_file.write_text(config_content)

        with patch.dict(os.environ, {
            'HOME': '/home/user',
            'PROJECT': '/workspace/myproject'
        }):
            configs = ConfigParser.parse_config(config_file)

        assert len(configs) == 2

        # Directory (trailing slash preserved)
        assert configs[0].source_path == Path('/home/user/config')
        assert configs[0].is_directory

        # File (no trailing slash)
        assert configs[1].source_path == Path('/workspace/myproject/src/main/resources/app.yml')
        assert not configs[1].is_directory
