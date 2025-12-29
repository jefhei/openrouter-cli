"""Configuration management for OpenRouter CLI."""

import json
import os
from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    """Authentication configuration."""

    api_key: str | None = Field(default=None, description="OpenRouter API key")


class DefaultsConfig(BaseModel):
    """Default settings configuration."""

    model: str = Field(default="openai/gpt-4o-mini", description="Default model")
    temperature: float = Field(default=1.0, description="Default temperature")
    max_tokens: int = Field(default=4096, description="Default max tokens")
    stream: bool = Field(default=True, description="Stream responses by default")
    top_p: float | None = Field(default=None, description="Default top_p")
    top_k: int | None = Field(default=None, description="Default top_k")
    frequency_penalty: float | None = Field(default=None, description="Default frequency penalty")
    presence_penalty: float | None = Field(default=None, description="Default presence penalty")


class HeadersConfig(BaseModel):
    """HTTP headers configuration."""

    app_name: str | None = Field(default=None, description="Application name")
    app_url: str | None = Field(default=None, description="Application URL")


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

    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication settings")
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig, description="Default settings")
    headers: HeadersConfig = Field(default_factory=HeadersConfig, description="HTTP headers")
    mcp: MCPConfig = Field(default_factory=MCPConfig, description="MCP configuration")


class ConfigManager:
    """Manages CLI configuration."""

    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "openrouter"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
    DEFAULT_MCP_FILE = DEFAULT_CONFIG_DIR / "mcp.json"
    CONVERSATIONS_DIR = DEFAULT_CONFIG_DIR / "conversations"

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

    def __init__(self, config_path: Path | None = None):
        """Initialize the config manager."""
        self.config_path = config_path or self.DEFAULT_CONFIG_FILE
        self._config: Config | None = None
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure configuration directories exist."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> Config:
        """Load configuration from file and environment."""
        config_dict: dict[str, Any] = {}

        # Load from file if exists
        if self.config_path.exists():
            try:
                config_dict = toml.load(self.config_path)
            except Exception:
                pass

        # Load MCP config from separate file if exists
        mcp_config_path = Path(os.environ.get("OPENROUTER_MCP_CONFIG", self.DEFAULT_MCP_FILE))
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
            except Exception:
                pass

        # Override with environment variables
        for env_var, config_path in self.ENV_VARS.items():
            value = os.environ.get(env_var)
            if value and config_path:
                section, key = config_path
                if section not in config_dict:
                    config_dict[section] = {}
                config_dict[section][key] = value

        return Config.model_validate(config_dict)

    def save(self) -> None:
        """Save configuration to file."""
        config_dict = self.config.model_dump(exclude_none=True, exclude_unset=True)
        with open(self.config_path, "w") as f:
            toml.dump(config_dict, f)

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
        """Set a configuration value by dot-notation key."""
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

        # Reload config
        self._config = Config.model_validate(config_dict)
        self.save()

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
