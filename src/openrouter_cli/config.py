"""Configuration management for OpenRouter CLI."""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field, field_validator, model_validator

# Configure module logger
logger = logging.getLogger(__name__)

# Current configuration schema version
CONFIG_SCHEMA_VERSION = 1


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""

    pass


class AuthConfig(BaseModel):
    """Authentication configuration."""

    api_key: str | None = Field(default=None, description="OpenRouter API key")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate API key format.

        OpenRouter API keys typically start with 'sk-or-' prefix.
        We allow None for unconfigured state, but validate format if provided.
        """
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        # OpenRouter API keys start with 'sk-or-' (versioned like 'sk-or-v1-')
        if not v.startswith("sk-or-"):
            raise ValueError(
                "Invalid API key format. OpenRouter API keys should start with 'sk-or-'. "
                "Get your API key from https://openrouter.ai/keys"
            )

        # Basic length check - keys are typically 50+ characters
        if len(v) < 20:
            raise ValueError("API key appears too short. Please check your API key.")

        return v


class DefaultsConfig(BaseModel):
    """Default settings configuration."""

    model: str = Field(default="openai/gpt-4o-mini", description="Default model")
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Default temperature (0.0-2.0)",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=1000000,
        description="Default max tokens",
    )
    stream: bool = Field(default=True, description="Stream responses by default")
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Default top_p (0.0-1.0)",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        description="Default top_k (>= 1)",
    )
    frequency_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Default frequency penalty (-2.0 to 2.0)",
    )
    presence_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Default presence penalty (-2.0 to 2.0)",
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model name format.

        Model names should be in 'provider/model-name' format.
        Examples: 'openai/gpt-4o', 'anthropic/claude-sonnet-4', 'google/gemini-pro'
        """
        v = v.strip()
        if not v:
            raise ValueError("Model name cannot be empty")

        # Model format: provider/model-name
        # Allow alphanumeric, hyphens, underscores, dots, and colons (for versions)
        pattern = r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9._:-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid model format: '{v}'. "
                "Model names should be in 'provider/model-name' format "
                "(e.g., 'openai/gpt-4o', 'anthropic/claude-sonnet-4')"
            )

        return v


class HeadersConfig(BaseModel):
    """HTTP headers configuration."""

    app_name: str | None = Field(default=None, description="Application name")
    app_url: str | None = Field(default=None, description="Application URL")

    @field_validator("app_url")
    @classmethod
    def validate_app_url(cls, v: str | None) -> str | None:
        """Validate app URL format."""
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        # Basic URL validation
        if not v.startswith(("http://", "https://")):
            raise ValueError("app_url must start with 'http://' or 'https://'")

        return v


class MCPServerConfig(BaseModel):
    """MCP server configuration."""

    enabled: bool = Field(default=False, description="Whether server is enabled")
    command: str = Field(description="Command to run server")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    allowed_directories: list[str] = Field(
        default_factory=list, description="Allowed directories for filesystem server"
    )
    allowed_tools: list[str] | None = Field(default=None, description="Allowed tools")
    blocked_tools: list[str] | None = Field(default=None, description="Blocked tools")

    @model_validator(mode="after")
    def validate_tool_lists(self) -> "MCPServerConfig":
        """Validate that allowed_tools and blocked_tools are not both set."""
        if self.allowed_tools is not None and self.blocked_tools is not None:
            raise ValueError("Cannot specify both allowed_tools and blocked_tools")
        return self


class MCPSettingsConfig(BaseModel):
    """MCP settings configuration."""

    confirm_writes: bool = Field(default=False, description="Confirm write operations")
    confirm_deletes: bool = Field(default=False, description="Confirm delete operations")


class MCPConfig(BaseModel):
    """MCP configuration."""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict, description="MCP servers")
    settings: MCPSettingsConfig = Field(default_factory=MCPSettingsConfig, description="MCP settings")


class Config(BaseModel):
    """Main configuration model."""

    # Schema version for migrations
    schema_version: int = Field(default=CONFIG_SCHEMA_VERSION, description="Configuration schema version")

    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication settings")
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig, description="Default settings")
    headers: HeadersConfig = Field(default_factory=HeadersConfig, description="HTTP headers")
    mcp: MCPConfig = Field(default_factory=MCPConfig, description="MCP configuration")


def migrate_config(config_dict: dict[str, Any], from_version: int) -> dict[str, Any]:
    """Migrate configuration from an older schema version.

    Args:
        config_dict: The configuration dictionary to migrate
        from_version: The version to migrate from

    Returns:
        The migrated configuration dictionary
    """
    # Future migrations go here
    # Example:
    # if from_version < 2:
    #     # Migration from v1 to v2
    #     if "old_key" in config_dict:
    #         config_dict["new_key"] = config_dict.pop("old_key")
    #     from_version = 2

    config_dict["schema_version"] = CONFIG_SCHEMA_VERSION
    return config_dict


class ConfigManager:
    """Manages CLI configuration."""

    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "openrouter"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
    DEFAULT_MCP_FILE = DEFAULT_CONFIG_DIR / "mcp.json"
    CONVERSATIONS_DIR = DEFAULT_CONFIG_DIR / "conversations"
    BACKUP_DIR = DEFAULT_CONFIG_DIR / "backups"

    # Environment variable mappings
    ENV_VARS = {
        "OPENROUTER_API_KEY": ("auth", "api_key"),
        "OPENROUTER_MODEL": ("defaults", "model"),
        "OPENROUTER_BASE_URL": None,  # Special handling
        "OPENROUTER_TIMEOUT": None,
        "OPENROUTER_MAX_RETRIES": None,
        "OPENROUTER_MCP_ENABLED": None,
        "OPENROUTER_MCP_CONFIG": None,
        "OPENROUTER_MCP_TIMEOUT": None,
        "OPENROUTER_MCP_LOG_LEVEL": None,
    }

    # Valid configuration keys for set() validation
    VALID_KEYS = {
        "auth.api_key",
        "defaults.model",
        "defaults.temperature",
        "defaults.max_tokens",
        "defaults.stream",
        "defaults.top_p",
        "defaults.top_k",
        "defaults.frequency_penalty",
        "defaults.presence_penalty",
        "headers.app_name",
        "headers.app_url",
        "mcp.settings.confirm_writes",
        "mcp.settings.confirm_deletes",
    }

    def __init__(self, config_path: Path | None = None):
        """Initialize the config manager."""
        self.config_path = config_path or self.DEFAULT_CONFIG_FILE
        self._config: Config | None = None
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure configuration directories exist."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> Config:
        """Load configuration from file and environment.

        Raises:
            ConfigLoadError: If the configuration file cannot be parsed
            ConfigValidationError: If the configuration is invalid
        """
        config_dict: dict[str, Any] = {}

        # Load from file if exists
        if self.config_path.exists():
            try:
                config_dict = toml.load(self.config_path)
            except toml.TomlDecodeError as e:
                error_msg = f"Failed to parse config file {self.config_path}: {e}"
                logger.error(error_msg)
                raise ConfigLoadError(error_msg) from e
            except PermissionError as e:
                error_msg = f"Permission denied reading config file {self.config_path}: {e}"
                logger.error(error_msg)
                raise ConfigLoadError(error_msg) from e
            except Exception as e:
                error_msg = f"Unexpected error loading config file {self.config_path}: {e}"
                logger.error(error_msg)
                raise ConfigLoadError(error_msg) from e

        # Check for schema migration
        file_version = config_dict.get("schema_version", 0)
        if file_version < CONFIG_SCHEMA_VERSION:
            logger.info(f"Migrating config from version {file_version} to {CONFIG_SCHEMA_VERSION}")
            config_dict = migrate_config(config_dict, file_version)

        # Load MCP config from separate file if exists
        mcp_config_path = Path(os.environ.get("OPENROUTER_MCP_CONFIG", str(self.DEFAULT_MCP_FILE)))
        if mcp_config_path.exists() and "mcp" not in config_dict:
            try:
                with open(mcp_config_path) as f:
                    mcp_data = json.load(f)
                if "mcpServers" in mcp_data:
                    config_dict["mcp"] = {"servers": {}}
                    for name, server in mcp_data["mcpServers"].items():
                        config_dict["mcp"]["servers"][name] = {
                            "enabled": True,
                            "command": server.get("command", ""),
                            "args": server.get("args", []),
                            "env": server.get("env", {}),
                        }
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse MCP config file {mcp_config_path}: {e}"
                logger.warning(error_msg)
                load_errors.append(error_msg)
            except Exception as e:
                error_msg = f"Error loading MCP config file {mcp_config_path}: {e}"
                logger.warning(error_msg)
                load_errors.append(error_msg)

        # Override with environment variables
        for env_var, config_path in self.ENV_VARS.items():
            value = os.environ.get(env_var)
            if value and config_path:
                section, key = config_path
                if section not in config_dict:
                    config_dict[section] = {}
                config_dict[section][key] = value

        # Validate and create config
        try:
            return Config.model_validate(config_dict)
        except Exception as e:
            error_msg = f"Configuration validation failed: {e}"
            logger.error(error_msg)
            raise ConfigValidationError(error_msg) from e

    def save(self) -> None:
        """Save configuration to file."""
        config_dict = self.config.model_dump(exclude_none=True, exclude_unset=True)
        with open(self.config_path, "w") as f:
            toml.dump(config_dict, f)

    def backup(self) -> Path:
        """Create a backup of the current configuration.

        Returns:
            Path to the backup file
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"No configuration file to backup at {self.config_path}")

        # Use microseconds for uniqueness to avoid overwriting backups made in same second
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self.BACKUP_DIR / f"config_{timestamp}.toml"
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Created configuration backup at {backup_path}")
        return backup_path

    def restore(self, backup_path: Path) -> None:
        """Restore configuration from a backup.

        Args:
            backup_path: Path to the backup file to restore

        Raises:
            FileNotFoundError: If the backup file doesn't exist
            ConfigValidationError: If the backup contains invalid configuration
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Validate backup before restoring
        try:
            backup_dict = toml.load(backup_path)
            Config.model_validate(backup_dict)
        except Exception as e:
            raise ConfigValidationError(f"Invalid backup file: {e}") from e

        # Create backup of current config before restoring
        if self.config_path.exists():
            self.backup()

        shutil.copy2(backup_path, self.config_path)
        self._config = None  # Force reload
        logger.info(f"Restored configuration from {backup_path}")

    def list_backups(self) -> list[Path]:
        """List available configuration backups.

        Returns:
            List of backup file paths, sorted by date (newest first)
        """
        backups = list(self.BACKUP_DIR.glob("config_*.toml"))
        return sorted(backups, reverse=True)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key."""
        parts = key.split(".")
        obj: Any = self.config
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return default
        return obj

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by dot-notation key.

        Args:
            key: Dot-notation key (e.g., 'defaults.temperature')
            value: Value to set

        Raises:
            ConfigValidationError: If the key is invalid or value fails validation
        """
        # Validate key is a known configuration key (except for mcp.servers.*)
        if not key.startswith("mcp.servers.") and key not in self.VALID_KEYS:
            valid_keys_str = ", ".join(sorted(self.VALID_KEYS))
            raise ConfigValidationError(
                f"Unknown configuration key: '{key}'. Valid keys are: {valid_keys_str}"
            )

        parts = key.split(".")
        config_dict = self.config.model_dump()

        # Navigate to parent
        obj = config_dict
        for part in parts[:-1]:
            if part not in obj:
                obj[part] = {}
            obj = obj[part]

        # Set value
        obj[parts[-1]] = value

        # Validate the new configuration
        try:
            self._config = Config.model_validate(config_dict)
        except Exception as e:
            raise ConfigValidationError(f"Invalid value for '{key}': {e}") from e

        self.save()

    def validate(self) -> list[str]:
        """Validate the current configuration and return any warnings.

        Returns:
            List of warning messages (empty if no issues)
        """
        warnings: list[str] = []

        # Check API key
        if not self.get_api_key():
            warnings.append(
                "No API key configured. Set OPENROUTER_API_KEY environment variable "
                "or run 'openrouter config set auth.api_key <your-key>'"
            )

        # Check for deprecated settings or other issues
        # (Add more checks as needed)

        return warnings

    def get_api_key(self) -> str | None:
        """Get the API key from config or environment."""
        return os.environ.get("OPENROUTER_API_KEY") or self.config.auth.api_key

    def get_base_url(self) -> str:
        """Get the API base URL."""
        return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    def get_timeout(self) -> int:
        """Get the request timeout in seconds."""
        return int(os.environ.get("OPENROUTER_TIMEOUT", "120"))

    def get_max_retries(self) -> int:
        """Get the maximum number of retries."""
        return int(os.environ.get("OPENROUTER_MAX_RETRIES", "3"))

    def get_mcp_timeout(self) -> int:
        """Get MCP server timeout in seconds."""
        return int(os.environ.get("OPENROUTER_MCP_TIMEOUT", "30"))

    def get_mcp_log_level(self) -> str:
        """Get MCP log level."""
        return os.environ.get("OPENROUTER_MCP_LOG_LEVEL", "warn")


# Global config manager instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get or create the global config manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
