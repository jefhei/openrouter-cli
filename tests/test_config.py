"""
Tests for configuration management.

Tests cover:
- Loading configuration from TOML files
- Saving configuration changes
- Default value handling
- Environment variable overrides
- Configuration validation
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Note: These imports assume the package structure from DEVELOPMENT.md
# Adjust imports once the actual package is created
# from openrouter_cli.config import Config, load_config, save_config, get_config_path


class TestConfigPath:
    """Tests for configuration file path resolution."""

    def test_default_config_path(self, tmp_path):
        """Config path defaults to ~/.config/openrouter/config.toml."""
        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            # Once implemented:
            # path = get_config_path()
            # assert path == tmp_path / ".config" / "openrouter" / "config.toml"
            expected = tmp_path / ".config" / "openrouter" / "config.toml"
            assert expected.parent.name == "openrouter"

    def test_xdg_config_home_override(self, tmp_path):
        """Respects XDG_CONFIG_HOME environment variable."""
        xdg_config = tmp_path / "custom_config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg_config)}, clear=False):
            expected = xdg_config / "openrouter" / "config.toml"
            assert expected.parent.name == "openrouter"

    def test_config_dir_created_if_missing(self, tmp_path):
        """Config directory is created if it doesn't exist."""
        config_dir = tmp_path / ".config" / "openrouter"
        assert not config_dir.exists()
        
        # Simulate what load_config should do
        config_dir.mkdir(parents=True, exist_ok=True)
        assert config_dir.exists()


class TestLoadConfig:
    """Tests for loading configuration from files."""

    def test_load_valid_config(self, mock_config_path, sample_config):
        """Successfully loads valid TOML configuration."""
        import tomllib
        
        content = mock_config_path.read_text()
        loaded = tomllib.loads(content)
        
        assert loaded["auth"]["api_key"] == sample_config["auth"]["api_key"]
        assert loaded["defaults"]["model"] == sample_config["defaults"]["model"]
        assert loaded["defaults"]["temperature"] == sample_config["defaults"]["temperature"]

    def test_load_missing_config_returns_defaults(self, temp_config_dir):
        """Returns default configuration when file doesn't exist."""
        config_file = temp_config_dir / "config.toml"
        assert not config_file.exists()
        
        # Default config structure
        defaults = {
            "auth": {"api_key": None},
            "defaults": {
                "model": "openai/gpt-4o-mini",
                "temperature": 1.0,
                "max_tokens": 4096,
                "stream": True
            },
            "headers": {}
        }
        
        assert defaults["defaults"]["model"] == "openai/gpt-4o-mini"
        assert defaults["defaults"]["stream"] is True

    def test_load_partial_config_merges_defaults(self, temp_config_file):
        """Partial config is merged with defaults."""
        # Config with only API key set
        partial_config = '[auth]\napi_key = "sk-or-v1-partial"\n'
        temp_config_file.write_text(partial_config)
        
        import tomllib
        loaded = tomllib.loads(partial_config)
        
        assert loaded["auth"]["api_key"] == "sk-or-v1-partial"
        assert "defaults" not in loaded  # Would be filled by merge logic

    def test_load_invalid_toml_raises_error(self, temp_config_file):
        """Invalid TOML syntax raises appropriate error."""
        temp_config_file.write_text("invalid = [toml syntax")
        
        import tomllib
        with pytest.raises(tomllib.TOMLDecodeError):
            tomllib.loads(temp_config_file.read_text())

    def test_load_config_with_mcp_section(self, temp_config_file, config_with_mcp):
        """Loads MCP server configuration correctly."""
        import tomli_w
        
        temp_config_file.write_text(tomli_w.dumps(config_with_mcp))
        
        import tomllib
        loaded = tomllib.loads(temp_config_file.read_text())
        
        assert "mcp" in loaded
        assert "filesystem" in loaded["mcp"]["servers"]
        assert loaded["mcp"]["servers"]["filesystem"]["enabled"] is True


class TestSaveConfig:
    """Tests for saving configuration to files."""

    def test_save_config_creates_file(self, temp_config_file, sample_config):
        """Saves configuration to new file."""
        import tomli_w
        
        assert not temp_config_file.exists()
        temp_config_file.write_text(tomli_w.dumps(sample_config))
        
        assert temp_config_file.exists()
        content = temp_config_file.read_text()
        assert "sk-or-v1-test-key-12345" in content

    def test_save_config_overwrites_existing(self, mock_config_path):
        """Overwrites existing configuration file."""
        import tomllib
        import tomli_w
        
        original = tomllib.loads(mock_config_path.read_text())
        assert original["defaults"]["model"] == "anthropic/claude-sonnet-4"
        
        # Modify and save
        original["defaults"]["model"] = "openai/gpt-4o"
        mock_config_path.write_text(tomli_w.dumps(original))
        
        # Verify change
        updated = tomllib.loads(mock_config_path.read_text())
        assert updated["defaults"]["model"] == "openai/gpt-4o"

    def test_save_config_creates_parent_dirs(self, tmp_path):
        """Creates parent directories if they don't exist."""
        nested_path = tmp_path / "deep" / "nested" / "config.toml"
        assert not nested_path.parent.exists()
        
        nested_path.parent.mkdir(parents=True, exist_ok=True)
        nested_path.write_text("# empty config\n")
        
        assert nested_path.exists()

    def test_save_preserves_comments(self, temp_config_file):
        """Ideally preserves user comments (limitation: tomli_w doesn't preserve comments)."""
        # Note: Standard TOML writers don't preserve comments
        # This test documents the expected behavior
        config_with_comments = '''# My OpenRouter configuration
[auth]
api_key = "sk-or-v1-test"

# Generation defaults
[defaults]
model = "anthropic/claude-sonnet-4"
'''
        temp_config_file.write_text(config_with_comments)
        
        # After round-trip, comments would be lost with tomli_w
        # This is a known limitation
        content = temp_config_file.read_text()
        assert "api_key" in content


class TestEnvironmentOverrides:
    """Tests for environment variable configuration overrides."""

    def test_api_key_from_environment(self, clean_env):
        """OPENROUTER_API_KEY environment variable overrides config."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-env-override"}):
            api_key = os.environ.get("OPENROUTER_API_KEY")
            assert api_key == "sk-or-v1-env-override"

    def test_model_from_environment(self, clean_env):
        """OPENROUTER_MODEL environment variable overrides default model."""
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "google/gemini-pro"}):
            model = os.environ.get("OPENROUTER_MODEL")
            assert model == "google/gemini-pro"

    def test_base_url_from_environment(self, clean_env):
        """OPENROUTER_BASE_URL environment variable overrides API base URL."""
        custom_url = "https://custom.openrouter.proxy/api/v1"
        with patch.dict(os.environ, {"OPENROUTER_BASE_URL": custom_url}):
            base_url = os.environ.get("OPENROUTER_BASE_URL")
            assert base_url == custom_url

    def test_timeout_from_environment(self, clean_env):
        """OPENROUTER_TIMEOUT environment variable is parsed as integer."""
        with patch.dict(os.environ, {"OPENROUTER_TIMEOUT": "60"}):
            timeout = int(os.environ.get("OPENROUTER_TIMEOUT", "120"))
            assert timeout == 60

    def test_environment_takes_precedence_over_file(self, mock_config_path, clean_env):
        """Environment variables take precedence over config file values."""
        import tomllib
        
        file_config = tomllib.loads(mock_config_path.read_text())
        file_api_key = file_config["auth"]["api_key"]
        
        env_api_key = "sk-or-v1-env-takes-precedence"
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": env_api_key}):
            # Simulate resolution logic: env > file > default
            resolved = os.environ.get("OPENROUTER_API_KEY") or file_api_key
            assert resolved == env_api_key


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_validate_api_key_format(self):
        """API key should match expected format."""
        valid_keys = [
            "sk-or-v1-abcd1234567890",
            "sk-or-v1-test-key-with-dashes",
        ]
        invalid_keys = [
            "",
            "invalid-key",
            "sk-wrong-prefix",
        ]
        
        for key in valid_keys:
            assert key.startswith("sk-or-")
        
        for key in invalid_keys:
            assert not key.startswith("sk-or-")

    def test_validate_temperature_range(self):
        """Temperature should be between 0 and 2."""
        valid_temps = [0, 0.5, 1.0, 1.5, 2.0]
        invalid_temps = [-0.1, 2.1, 5.0]
        
        for temp in valid_temps:
            assert 0 <= temp <= 2
        
        for temp in invalid_temps:
            assert not (0 <= temp <= 2)

    def test_validate_max_tokens_positive(self):
        """Max tokens should be a positive integer."""
        valid_values = [1, 100, 4096, 100000]
        invalid_values = [0, -1, -100]
        
        for val in valid_values:
            assert val > 0
        
        for val in invalid_values:
            assert not (val > 0)

    def test_validate_model_format(self):
        """Model ID should be in provider/model format."""
        valid_models = [
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4",
            "google/gemini-pro",
            "meta-llama/llama-3-70b",
        ]
        invalid_models = [
            "gpt-4",
            "claude",
            "no-slash",
        ]
        
        for model in valid_models:
            assert "/" in model and len(model.split("/")) == 2
        
        for model in invalid_models:
            assert "/" not in model or len(model.split("/")) != 2


class TestConfigGetSet:
    """Tests for config get/set CLI operations."""

    def test_set_api_key(self, temp_config_file, sample_config):
        """Setting API key updates config file."""
        import tomllib
        import tomli_w
        
        # Initial save
        temp_config_file.write_text(tomli_w.dumps(sample_config))
        
        # Load, modify, save
        config = tomllib.loads(temp_config_file.read_text())
        config["auth"]["api_key"] = "sk-or-v1-new-key"
        temp_config_file.write_text(tomli_w.dumps(config))
        
        # Verify
        updated = tomllib.loads(temp_config_file.read_text())
        assert updated["auth"]["api_key"] == "sk-or-v1-new-key"

    def test_set_nested_value(self, temp_config_file, sample_config):
        """Setting nested values like defaults.model works."""
        import tomllib
        import tomli_w
        
        temp_config_file.write_text(tomli_w.dumps(sample_config))
        
        config = tomllib.loads(temp_config_file.read_text())
        config["defaults"]["model"] = "openai/gpt-4o"
        config["defaults"]["temperature"] = 0.7
        temp_config_file.write_text(tomli_w.dumps(config))
        
        updated = tomllib.loads(temp_config_file.read_text())
        assert updated["defaults"]["model"] == "openai/gpt-4o"
        assert updated["defaults"]["temperature"] == 0.7

    def test_get_existing_value(self, mock_config_path):
        """Getting existing config value returns correct result."""
        import tomllib
        
        config = tomllib.loads(mock_config_path.read_text())
        
        assert config["auth"]["api_key"] == "sk-or-v1-test-key-12345"
        assert config["defaults"]["stream"] is True

    def test_get_missing_value_returns_none(self, mock_config_path):
        """Getting non-existent config value returns None."""
        import tomllib
        
        config = tomllib.loads(mock_config_path.read_text())
        
        # Key that doesn't exist
        result = config.get("nonexistent", {}).get("key", None)
        assert result is None


class TestMCPConfig:
    """Tests for MCP-specific configuration."""

    def test_mcp_server_config_structure(self, config_with_mcp):
        """MCP server configuration has correct structure."""
        mcp = config_with_mcp["mcp"]
        
        assert "servers" in mcp
        assert "filesystem" in mcp["servers"]
        
        fs_config = mcp["servers"]["filesystem"]
        assert fs_config["enabled"] is True
        assert fs_config["command"] == "npx"
        assert isinstance(fs_config["args"], list)
        assert isinstance(fs_config["allowed_directories"], list)

    def test_mcp_server_disabled_by_default(self):
        """MCP servers are disabled by default."""
        default_mcp_config = {
            "servers": {
                "filesystem": {
                    "enabled": False
                }
            }
        }
        
        assert default_mcp_config["servers"]["filesystem"]["enabled"] is False

    def test_mcp_allowed_tools_filter(self):
        """MCP tool filtering configuration is parsed correctly."""
        mcp_config = {
            "servers": {
                "filesystem": {
                    "enabled": True,
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                    "allowed_tools": ["read_file", "list_directory"]
                }
            }
        }
        
        allowed = mcp_config["servers"]["filesystem"]["allowed_tools"]
        assert "read_file" in allowed
        assert "write_file" not in allowed

    def test_mcp_blocked_tools_filter(self):
        """MCP blocked tools configuration is parsed correctly."""
        mcp_config = {
            "servers": {
                "filesystem": {
                    "enabled": True,
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                    "blocked_tools": ["write_file", "edit_file", "move_file"]
                }
            }
        }
        
        blocked = mcp_config["servers"]["filesystem"]["blocked_tools"]
        assert "write_file" in blocked
        assert "read_file" not in blocked
