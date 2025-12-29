"""
Pytest fixtures for OpenRouter CLI tests.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


# =============================================================================
# CLI Runner Fixtures
# =============================================================================


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def isolated_runner():
    """Click CLI runner with isolated filesystem."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary configuration directory."""
    config_dir = tmp_path / ".config" / "openrouter"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Temporary config.toml file path."""
    return temp_config_dir / "config.toml"


@pytest.fixture
def sample_config():
    """Sample configuration dictionary."""
    return {
        "auth": {
            "api_key": "sk-or-v1-test-key-12345"
        },
        "defaults": {
            "model": "anthropic/claude-sonnet-4",
            "temperature": 1.0,
            "max_tokens": 4096,
            "stream": True
        },
        "headers": {
            "app_name": "test-cli-app",
            "app_url": "https://test.example.com"
        }
    }


@pytest.fixture
def sample_config_toml():
    """Sample configuration as TOML string."""
    return '''[auth]
api_key = "sk-or-v1-test-key-12345"

[defaults]
model = "anthropic/claude-sonnet-4"
temperature = 1.0
max_tokens = 4096
stream = true

[headers]
app_name = "test-cli-app"
app_url = "https://test.example.com"
'''


@pytest.fixture
def config_with_mcp():
    """Configuration with MCP servers enabled."""
    return {
        "auth": {
            "api_key": "sk-or-v1-test-key-12345"
        },
        "defaults": {
            "model": "openai/gpt-4o-mini",
            "stream": True
        },
        "mcp": {
            "servers": {
                "filesystem": {
                    "enabled": True,
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/test"],
                    "allowed_directories": ["/tmp/test"]
                }
            }
        }
    }


@pytest.fixture
def mock_config_path(temp_config_file, sample_config_toml):
    """Write sample config and return path."""
    temp_config_file.write_text(sample_config_toml)
    return temp_config_file


# =============================================================================
# Environment Fixtures
# =============================================================================


@pytest.fixture
def clean_env():
    """Clean environment without OpenRouter variables."""
    env_vars = [
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_TIMEOUT",
        "OPENROUTER_MAX_RETRIES",
        "OPENROUTER_MCP_ENABLED",
        "OPENROUTER_MCP_CONFIG",
    ]
    with patch.dict(os.environ, {}, clear=False):
        for var in env_vars:
            os.environ.pop(var, None)
        yield


@pytest.fixture
def env_with_api_key():
    """Environment with API key set."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-env-key-67890"}):
        yield


# =============================================================================
# API Response Fixtures
# =============================================================================


@pytest.fixture
def mock_models_response():
    """Load mock models list response."""
    mock_file = Path(__file__).parent / "mocks" / "models_list.json"
    if mock_file.exists():
        return json.loads(mock_file.read_text())
    # Fallback inline mock
    return {
        "data": [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "context_length": 128000,
                "pricing": {"prompt": "0.000005", "completion": "0.000015"}
            },
            {
                "id": "anthropic/claude-sonnet-4",
                "name": "Claude Sonnet 4",
                "context_length": 200000,
                "pricing": {"prompt": "0.000003", "completion": "0.000015"}
            }
        ]
    }


@pytest.fixture
def mock_chat_response():
    """Load mock chat completion response."""
    mock_file = Path(__file__).parent / "mocks" / "chat_completion.json"
    if mock_file.exists():
        return json.loads(mock_file.read_text())
    # Fallback inline mock
    return {
        "id": "gen-test-12345",
        "model": "anthropic/claude-sonnet-4",
        "object": "chat.completion",
        "created": 1234567890,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18
        }
    }


@pytest.fixture
def mock_chat_stream_chunks():
    """Mock streaming response chunks."""
    return [
        {"id": "gen-test-12345", "choices": [{"delta": {"role": "assistant"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {"content": "Hello"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {"content": "!"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {"content": " How"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {"content": " can"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {"content": " I"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {"content": " help?"}, "index": 0}]},
        {"id": "gen-test-12345", "choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]},
    ]


@pytest.fixture
def mock_tool_call_response():
    """Mock response with tool call."""
    return {
        "id": "gen-test-tool-12345",
        "model": "anthropic/claude-sonnet-4",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path": "/tmp/test/example.txt"}'
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls"
            }
        ],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75
        }
    }


@pytest.fixture
def mock_error_response():
    """Mock API error response."""
    return {
        "error": {
            "code": 401,
            "message": "Invalid API key provided",
            "type": "authentication_error"
        }
    }


# =============================================================================
# HTTP Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API tests."""
    with patch("httpx.AsyncClient") as mock:
        yield mock


@pytest.fixture
def mock_requests():
    """Mock requests/httpx for synchronous API calls."""
    with patch("httpx.Client") as mock:
        client_instance = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=client_instance)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield client_instance


# =============================================================================
# Conversation Fixtures
# =============================================================================


@pytest.fixture
def temp_conversations_dir(temp_config_dir):
    """Temporary conversations storage directory."""
    conv_dir = temp_config_dir / "conversations"
    conv_dir.mkdir(parents=True)
    return conv_dir


@pytest.fixture
def sample_conversation():
    """Sample conversation history."""
    return {
        "id": "test-conversation-1",
        "name": "my-project",
        "model": "anthropic/claude-sonnet-4",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T11:45:00Z",
        "messages": [
            {"role": "user", "content": "Let's discuss the architecture"},
            {"role": "assistant", "content": "I'd be happy to help with the architecture..."},
            {"role": "user", "content": "What about the database layer?"},
            {"role": "assistant", "content": "For the database layer, I recommend..."}
        ],
        "metadata": {
            "total_tokens": 450,
            "estimated_cost": 0.00135
        }
    }


# =============================================================================
# MCP Fixtures
# =============================================================================


@pytest.fixture
def mock_mcp_tools():
    """Mock MCP filesystem tools."""
    return [
        {
            "name": "read_file",
            "description": "Read the contents of a file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["path"]
            }
        },
        {
            "name": "write_file",
            "description": "Write content to a file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "list_directory",
            "description": "List contents of a directory",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory"}
                },
                "required": ["path"]
            }
        }
    ]


@pytest.fixture
def mock_mcp_manager():
    """Mock MCP manager for testing."""
    manager = MagicMock()
    manager.is_running.return_value = True
    manager.get_tools.return_value = []
    manager.execute_tool.return_value = {"result": "success"}
    return manager
