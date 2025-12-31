"""Tests for configuration validation in OpenRouter CLI."""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from openrouter_cli.config import (
    AuthConfig,
    Config,
    ConfigLoadError,
    ConfigManager,
    ConfigValidationError,
    DefaultsConfig,
    HeadersConfig,
    MCPServerConfig,
    CONFIG_SCHEMA_VERSION,
    migrate_config,
)


class TestAuthConfigValidation:
    """Tests for API key validation."""

    def test_valid_api_key(self):
        """Test that valid API keys are accepted."""
        config = AuthConfig(api_key="sk-or-v1-1234567890abcdef1234567890abcdef")
        assert config.api_key.startswith("sk-or-")

    def test_api_key_none_allowed(self):
        """Test that None API key is allowed (unconfigured state)."""
        config = AuthConfig(api_key=None)
        assert config.api_key is None

    def test_api_key_empty_string_becomes_none(self):
        """Test that empty string API key becomes None."""
        config = AuthConfig(api_key="")
        assert config.api_key is None

    def test_api_key_whitespace_becomes_none(self):
        """Test that whitespace-only API key becomes None."""
        config = AuthConfig(api_key="   ")
        assert config.api_key is None

    def test_api_key_invalid_prefix(self):
        """Test that API keys without 'sk-or-' prefix are rejected."""
        with pytest.raises(ValueError, match="should start with 'sk-or-'"):
            AuthConfig(api_key="sk-wrong-prefix-1234567890")

    def test_api_key_too_short(self):
        """Test that very short API keys are rejected."""
        with pytest.raises(ValueError, match="appears too short"):
            AuthConfig(api_key="sk-or-short")

    def test_api_key_stripped(self):
        """Test that API keys are stripped of whitespace."""
        config = AuthConfig(api_key="  sk-or-v1-1234567890abcdef1234567890abcdef  ")
        assert not config.api_key.startswith(" ")
        assert not config.api_key.endswith(" ")


class TestDefaultsConfigValidation:
    """Tests for defaults configuration validation."""

    def test_valid_model_format(self):
        """Test that valid model names are accepted."""
        valid_models = [
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4",
            "google/gemini-pro",
            "meta-llama/llama-3-70b",
            "mistralai/mixtral-8x7b-instruct",
            "openai/gpt-4o-2024-05-13",
            "anthropic/claude-3.5-sonnet:beta",
        ]
        for model in valid_models:
            config = DefaultsConfig(model=model)
            assert config.model == model

    def test_invalid_model_no_provider(self):
        """Test that model names without provider are rejected."""
        with pytest.raises(ValueError, match="provider/model-name"):
            DefaultsConfig(model="gpt-4o")

    def test_invalid_model_empty(self):
        """Test that empty model names are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            DefaultsConfig(model="")

    def test_invalid_model_special_chars(self):
        """Test that model names with invalid characters are rejected."""
        with pytest.raises(ValueError, match="provider/model-name"):
            DefaultsConfig(model="openai/gpt 4o")  # space

    def test_temperature_valid_range(self):
        """Test that temperature in valid range is accepted."""
        config = DefaultsConfig(temperature=0.0)
        assert config.temperature == 0.0

        config = DefaultsConfig(temperature=1.0)
        assert config.temperature == 1.0

        config = DefaultsConfig(temperature=2.0)
        assert config.temperature == 2.0

    def test_temperature_below_range(self):
        """Test that temperature below 0 is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(temperature=-0.1)

    def test_temperature_above_range(self):
        """Test that temperature above 2 is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(temperature=2.1)

    def test_top_p_valid_range(self):
        """Test that top_p in valid range is accepted."""
        config = DefaultsConfig(top_p=0.0)
        assert config.top_p == 0.0

        config = DefaultsConfig(top_p=1.0)
        assert config.top_p == 1.0

    def test_top_p_below_range(self):
        """Test that top_p below 0 is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(top_p=-0.1)

    def test_top_p_above_range(self):
        """Test that top_p above 1 is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(top_p=1.1)

    def test_top_k_valid(self):
        """Test that valid top_k values are accepted."""
        config = DefaultsConfig(top_k=1)
        assert config.top_k == 1

        config = DefaultsConfig(top_k=100)
        assert config.top_k == 100

    def test_top_k_below_range(self):
        """Test that top_k below 1 is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(top_k=0)

    def test_max_tokens_valid(self):
        """Test that valid max_tokens values are accepted."""
        config = DefaultsConfig(max_tokens=1)
        assert config.max_tokens == 1

        config = DefaultsConfig(max_tokens=100000)
        assert config.max_tokens == 100000

    def test_max_tokens_below_range(self):
        """Test that max_tokens below 1 is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(max_tokens=0)

    def test_frequency_penalty_valid_range(self):
        """Test that frequency_penalty in valid range is accepted."""
        config = DefaultsConfig(frequency_penalty=-2.0)
        assert config.frequency_penalty == -2.0

        config = DefaultsConfig(frequency_penalty=2.0)
        assert config.frequency_penalty == 2.0

    def test_frequency_penalty_out_of_range(self):
        """Test that frequency_penalty out of range is rejected."""
        with pytest.raises(ValueError):
            DefaultsConfig(frequency_penalty=-2.1)

        with pytest.raises(ValueError):
            DefaultsConfig(frequency_penalty=2.1)

    def test_presence_penalty_valid_range(self):
        """Test that presence_penalty in valid range is accepted."""
        config = DefaultsConfig(presence_penalty=-2.0)
        assert config.presence_penalty == -2.0

        config = DefaultsConfig(presence_penalty=2.0)
        assert config.presence_penalty == 2.0


class TestHeadersConfigValidation:
    """Tests for headers configuration validation."""

    def test_valid_app_url(self):
        """Test that valid URLs are accepted."""
        config = HeadersConfig(app_url="https://example.com")
        assert config.app_url == "https://example.com"

        config = HeadersConfig(app_url="http://localhost:8080")
        assert config.app_url == "http://localhost:8080"

    def test_app_url_none_allowed(self):
        """Test that None URL is allowed."""
        config = HeadersConfig(app_url=None)
        assert config.app_url is None

    def test_app_url_empty_becomes_none(self):
        """Test that empty URL becomes None."""
        config = HeadersConfig(app_url="")
        assert config.app_url is None

    def test_app_url_invalid_protocol(self):
        """Test that URLs without http(s) are rejected."""
        with pytest.raises(ValueError, match="must start with"):
            HeadersConfig(app_url="ftp://example.com")


class TestMCPServerConfigValidation:
    """Tests for MCP server configuration validation."""

    def test_valid_mcp_server_config(self):
        """Test valid MCP server configuration."""
        config = MCPServerConfig(
            enabled=True,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"],
        )
        assert config.enabled is True
        assert config.command == "npx"

    def test_allowed_and_blocked_tools_mutually_exclusive(self):
        """Test that allowed_tools and blocked_tools cannot both be set."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            MCPServerConfig(
                command="npx",
                allowed_tools=["read_file"],
                blocked_tools=["write_file"],
            )

    def test_allowed_tools_only(self):
        """Test that allowed_tools alone is valid."""
        config = MCPServerConfig(
            command="npx",
            allowed_tools=["read_file", "list_directory"],
        )
        assert config.allowed_tools == ["read_file", "list_directory"]

    def test_blocked_tools_only(self):
        """Test that blocked_tools alone is valid."""
        config = MCPServerConfig(
            command="npx",
            blocked_tools=["write_file", "delete_file"],
        )
        assert config.blocked_tools == ["write_file", "delete_file"]


class TestConfigSchemaVersioning:
    """Tests for configuration schema versioning."""

    def test_default_schema_version(self):
        """Test that new configs have current schema version."""
        config = Config()
        assert config.schema_version == CONFIG_SCHEMA_VERSION

    def test_migrate_config_updates_version(self):
        """Test that migration updates schema version."""
        old_config = {"defaults": {"model": "openai/gpt-4o"}}
        migrated = migrate_config(old_config, 0)
        assert migrated["schema_version"] == CONFIG_SCHEMA_VERSION


class TestConfigManager:
    """Tests for ConfigManager functionality."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create a temporary config directory."""
        config_dir = tmp_path / ".config" / "openrouter"
        config_dir.mkdir(parents=True)
        return config_dir

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temporary directory."""
        config_path = temp_config_dir / "config.toml"
        manager = ConfigManager(config_path=config_path)
        # Note: Don't set BACKUP_DIR here - tests will set it as needed
        return manager

    def test_load_empty_config(self, config_manager):
        """Test loading when no config file exists."""
        config = config_manager.load()
        assert config.defaults.model == "openai/gpt-4o-mini"
        assert config.schema_version == CONFIG_SCHEMA_VERSION

    def test_load_valid_config(self, config_manager):
        """Test loading a valid config file."""
        config_data = {
            "auth": {"api_key": "sk-or-v1-test1234567890test1234567890"},
            "defaults": {"model": "anthropic/claude-sonnet-4", "temperature": 0.7},
        }
        with open(config_manager.config_path, "w") as f:
            toml.dump(config_data, f)

        config = config_manager.load()
        assert config.defaults.model == "anthropic/claude-sonnet-4"
        assert config.defaults.temperature == 0.7

    def test_load_invalid_toml(self, config_manager):
        """Test loading an invalid TOML file."""
        with open(config_manager.config_path, "w") as f:
            f.write("invalid toml [[[")

        # Should raise ConfigLoadError
        with pytest.raises(ConfigLoadError):
            config_manager.load()

    def test_load_invalid_values(self, config_manager):
        """Test loading config with invalid values."""
        config_data = {
            "defaults": {"temperature": 5.0},  # Invalid: above 2.0
        }
        with open(config_manager.config_path, "w") as f:
            toml.dump(config_data, f)

        with pytest.raises(ConfigValidationError):
            config_manager.load()

    def test_set_valid_value(self, config_manager):
        """Test setting a valid configuration value."""
        config_manager.set("defaults.temperature", 0.5)
        assert config_manager.config.defaults.temperature == 0.5

    def test_set_invalid_value(self, config_manager):
        """Test setting an invalid configuration value."""
        with pytest.raises(ConfigValidationError, match="Invalid value"):
            config_manager.set("defaults.temperature", 5.0)

    def test_set_unknown_key(self, config_manager):
        """Test setting an unknown configuration key."""
        with pytest.raises(ConfigValidationError, match="Unknown configuration key"):
            config_manager.set("unknown.key", "value")

    def test_set_mcp_server_allowed(self, config_manager):
        """Test that setting MCP server config is allowed."""
        # First create a complete server config via direct dict manipulation
        config_dict = config_manager.config.model_dump()
        config_dict["mcp"]["servers"]["test"] = {
            "enabled": True,
            "command": "npx",
            "args": ["-y", "test-server"],
            "env": {},
            "allowed_directories": [],
            "allowed_tools": None,
            "blocked_tools": None,
        }
        config_manager._config = Config.model_validate(config_dict)
        config_manager.save()

        # Now verify we can read it back
        config_manager._config = None  # Force reload
        assert "test" in config_manager.config.mcp.servers
        assert config_manager.config.mcp.servers["test"].enabled is True

    def test_backup_and_restore(self, config_manager, temp_config_dir):
        """Test configuration backup and restore."""
        # Set initial config
        config_manager.set("defaults.temperature", 0.8)

        # Manually set backup dir
        backup_dir = temp_config_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        original_backup_dir = ConfigManager.BACKUP_DIR
        ConfigManager.BACKUP_DIR = backup_dir

        try:
            # Create backup
            backup_path = config_manager.backup()
            assert backup_path.exists()

            # Change config
            config_manager.set("defaults.temperature", 0.5)
            assert config_manager.config.defaults.temperature == 0.5

            # Restore backup
            config_manager.restore(backup_path)

            # Force reload and verify
            config_manager._config = None
            assert config_manager.config.defaults.temperature == 0.8
        finally:
            ConfigManager.BACKUP_DIR = original_backup_dir

    def test_list_backups(self, config_manager, temp_config_dir):
        """Test listing configuration backups."""
        # Manually set backup dir
        backup_dir = temp_config_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        original_backup_dir = ConfigManager.BACKUP_DIR
        ConfigManager.BACKUP_DIR = backup_dir

        try:
            # Create some backups with delay to ensure different timestamps
            config_manager.set("defaults.temperature", 0.5)
            config_manager.backup()
            time.sleep(1.1)  # Ensure different timestamp (second resolution)
            config_manager.set("defaults.temperature", 0.6)
            config_manager.backup()

            backups = config_manager.list_backups()
            assert len(backups) >= 2
        finally:
            ConfigManager.BACKUP_DIR = original_backup_dir

    def test_validate_warns_missing_api_key(self, config_manager):
        """Test that validation warns about missing API key."""
        warnings = config_manager.validate()
        assert any("API key" in w for w in warnings)

    def test_env_var_override(self, config_manager, monkeypatch):
        """Test that environment variables override config file."""
        # Set in config file
        config_data = {
            "auth": {"api_key": "sk-or-v1-file1234567890file1234567890"},
        }
        with open(config_manager.config_path, "w") as f:
            toml.dump(config_data, f)

        # Override with env var
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-env12345678901234567890")
        config_manager._config = None  # Force reload

        # get_api_key should return env var
        assert config_manager.get_api_key() == "sk-or-v1-env12345678901234567890"


class TestConfigManagerMCPConfig:
    """Tests for ConfigManager MCP configuration loading."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create a temporary config directory."""
        config_dir = tmp_path / ".config" / "openrouter"
        config_dir.mkdir(parents=True)
        return config_dir

    def test_load_mcp_json_config(self, temp_config_dir, monkeypatch):
        """Test loading MCP config from separate JSON file."""
        config_path = temp_config_dir / "config.toml"
        mcp_path = temp_config_dir / "mcp.json"

        mcp_data = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home"],
                }
            }
        }
        with open(mcp_path, "w") as f:
            json.dump(mcp_data, f)

        # Point to the MCP config
        monkeypatch.setenv("OPENROUTER_MCP_CONFIG", str(mcp_path))

        # Create manager with custom path
        manager = ConfigManager(config_path=config_path)
        manager.DEFAULT_MCP_FILE = mcp_path

        config = manager.load()
        assert "filesystem" in config.mcp.servers
        assert config.mcp.servers["filesystem"].enabled is True


class TestIntegration:
    """Integration tests for the full configuration flow."""

    def test_full_config_roundtrip(self, tmp_path):
        """Test creating, saving, and loading configuration."""
        config_path = tmp_path / "config.toml"
        manager = ConfigManager(config_path=config_path)

        # Set various values
        manager.set("auth.api_key", "sk-or-v1-test1234567890test1234567890")
        manager.set("defaults.model", "anthropic/claude-sonnet-4")
        manager.set("defaults.temperature", 0.7)
        manager.set("defaults.max_tokens", 2048)

        # Create new manager and load
        manager2 = ConfigManager(config_path=config_path)
        config = manager2.load()

        assert config.auth.api_key == "sk-or-v1-test1234567890test1234567890"
        assert config.defaults.model == "anthropic/claude-sonnet-4"
        assert config.defaults.temperature == 0.7
        assert config.defaults.max_tokens == 2048


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
