"""Tests for tool call error handling in chat command."""

import json
import pytest
from unittest.mock import Mock, MagicMock


class TestParseToolCall:
    """Tests for parse_tool_call function."""

    def test_parse_valid_tool_call(self):
        """Test parsing a valid tool call dict."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "id": "call_123",
            "function": {
                "name": "mcp_filesystem_read_file",
                "arguments": '{"path": "/tmp/test.txt"}'
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["id"] == "call_123"
        assert result["name"] == "mcp_filesystem_read_file"
        assert result["arguments"] == {"path": "/tmp/test.txt"}
        assert result["error"] is None

    def test_parse_tool_call_with_dict_arguments(self):
        """Test parsing tool call when arguments is already a dict."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "id": "call_456",
            "function": {
                "name": "mcp_filesystem_list_directory",
                "arguments": {"path": "/home"}
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["arguments"] == {"path": "/home"}
        assert result["error"] is None

    def test_parse_tool_call_with_invalid_json_arguments(self):
        """Test parsing tool call with malformed JSON arguments."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "id": "call_789",
            "function": {
                "name": "test_tool",
                "arguments": '{"invalid": json}'  # Invalid JSON
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["id"] == "call_789"
        assert result["arguments"] == {}
        assert result["error"] is not None
        assert "JSON" in result["error"] or "parse" in result["error"].lower()

    def test_parse_tool_call_missing_id(self):
        """Test parsing tool call with missing id field."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "function": {
                "name": "test_tool",
                "arguments": "{}"
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["id"] == ""  # Should default to empty string
        assert result["error"] is None

    def test_parse_tool_call_missing_function(self):
        """Test parsing tool call with missing function field."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {"id": "call_123"}
        
        result = parse_tool_call(tool_call)
        
        assert result["error"] is not None
        assert "function" in result["error"].lower() or "missing" in result["error"].lower()

    def test_parse_tool_call_missing_function_name(self):
        """Test parsing tool call with missing function name."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "id": "call_123",
            "function": {
                "arguments": "{}"
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["error"] is not None
        assert "name" in result["error"].lower()

    def test_parse_tool_call_empty_arguments(self):
        """Test parsing tool call with empty arguments string."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "id": "call_123",
            "function": {
                "name": "test_tool",
                "arguments": ""
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["arguments"] == {}
        assert result["error"] is None

    def test_parse_tool_call_none_arguments(self):
        """Test parsing tool call with None arguments."""
        from openrouter_cli.commands.chat import parse_tool_call
        
        tool_call = {
            "id": "call_123",
            "function": {
                "name": "test_tool",
                "arguments": None
            }
        }
        
        result = parse_tool_call(tool_call)
        
        assert result["arguments"] == {}
        assert result["error"] is None


class TestParseMcpToolName:
    """Tests for parse_mcp_tool_name function."""

    def test_parse_valid_mcp_tool_name(self):
        """Test parsing a valid MCP tool name."""
        from openrouter_cli.commands.chat import parse_mcp_tool_name
        
        result = parse_mcp_tool_name("mcp_filesystem_read_file")
        
        assert result["server_name"] == "filesystem"
        assert result["tool_name"] == "read_file"
        assert result["error"] is None

    def test_parse_mcp_tool_name_with_underscores_in_tool(self):
        """Test parsing MCP tool name where tool name contains underscores."""
        from openrouter_cli.commands.chat import parse_mcp_tool_name
        
        result = parse_mcp_tool_name("mcp_github_create_pull_request")
        
        assert result["server_name"] == "github"
        assert result["tool_name"] == "create_pull_request"
        assert result["error"] is None

    def test_parse_non_mcp_tool_name(self):
        """Test parsing a non-MCP tool name."""
        from openrouter_cli.commands.chat import parse_mcp_tool_name
        
        result = parse_mcp_tool_name("get_weather")
        
        assert result["error"] is not None
        assert "mcp_" in result["error"].lower() or "not an mcp" in result["error"].lower()

    def test_parse_mcp_tool_name_missing_tool_part(self):
        """Test parsing MCP tool name with missing tool part."""
        from openrouter_cli.commands.chat import parse_mcp_tool_name
        
        result = parse_mcp_tool_name("mcp_filesystem")
        
        assert result["error"] is not None
        assert "format" in result["error"].lower() or "invalid" in result["error"].lower()

    def test_parse_mcp_tool_name_only_prefix(self):
        """Test parsing with only 'mcp_' prefix."""
        from openrouter_cli.commands.chat import parse_mcp_tool_name
        
        result = parse_mcp_tool_name("mcp_")
        
        assert result["error"] is not None

    def test_parse_empty_tool_name(self):
        """Test parsing empty tool name."""
        from openrouter_cli.commands.chat import parse_mcp_tool_name
        
        result = parse_mcp_tool_name("")
        
        assert result["error"] is not None


class TestExecuteToolCall:
    """Tests for execute_tool_call function."""

    def test_execute_mcp_tool_success(self):
        """Test successful MCP tool execution."""
        from openrouter_cli.commands.chat import execute_tool_call
        
        mock_manager = Mock()
        mock_manager.execute_tool.return_value = "File content here"
        
        result = execute_tool_call(
            func_name="mcp_filesystem_read_file",
            args={"path": "/tmp/test.txt"},
            mcp_manager=mock_manager,
        )
        
        assert result["success"] is True
        assert result["result"] == "File content here"
        assert result["error"] is None
        mock_manager.execute_tool.assert_called_once_with(
            "filesystem", "read_file", {"path": "/tmp/test.txt"}
        )

    def test_execute_mcp_tool_server_error(self):
        """Test MCP tool execution with server error."""
        from openrouter_cli.commands.chat import execute_tool_call
        from openrouter_cli.mcp.manager import MCPServerError
        
        mock_manager = Mock()
        mock_manager.execute_tool.side_effect = MCPServerError("Connection failed")
        
        result = execute_tool_call(
            func_name="mcp_filesystem_read_file",
            args={"path": "/tmp/test.txt"},
            mcp_manager=mock_manager,
        )
        
        assert result["success"] is False
        assert "Connection failed" in result["error"]

    def test_execute_mcp_tool_unexpected_error(self):
        """Test MCP tool execution with unexpected exception."""
        from openrouter_cli.commands.chat import execute_tool_call
        
        mock_manager = Mock()
        mock_manager.execute_tool.side_effect = RuntimeError("Unexpected error")
        
        result = execute_tool_call(
            func_name="mcp_filesystem_read_file",
            args={"path": "/tmp/test.txt"},
            mcp_manager=mock_manager,
        )
        
        assert result["success"] is False
        assert "Unexpected error" in result["error"] or "error" in result["error"].lower()

    def test_execute_non_mcp_tool_without_manager(self):
        """Test executing non-MCP tool without MCP manager."""
        from openrouter_cli.commands.chat import execute_tool_call
        
        result = execute_tool_call(
            func_name="get_weather",
            args={"city": "Tokyo"},
            mcp_manager=None,
        )
        
        assert result["success"] is False
        assert "unknown" in result["error"].lower() or "not supported" in result["error"].lower()

    def test_execute_invalid_mcp_tool_name_format(self):
        """Test executing tool with invalid MCP name format."""
        from openrouter_cli.commands.chat import execute_tool_call
        
        mock_manager = Mock()
        
        result = execute_tool_call(
            func_name="mcp_filesystem",  # Missing tool name part
            args={},
            mcp_manager=mock_manager,
        )
        
        assert result["success"] is False
        assert "format" in result["error"].lower() or "invalid" in result["error"].lower()

    def test_execute_mcp_tool_with_none_manager(self):
        """Test executing MCP tool when manager is None."""
        from openrouter_cli.commands.chat import execute_tool_call
        
        result = execute_tool_call(
            func_name="mcp_filesystem_read_file",
            args={"path": "/tmp/test.txt"},
            mcp_manager=None,
        )
        
        assert result["success"] is False
        assert "mcp" in result["error"].lower() or "not available" in result["error"].lower()


class TestFormatToolError:
    """Tests for format_tool_error function."""

    def test_format_json_parse_error(self):
        """Test formatting JSON parse error."""
        from openrouter_cli.commands.chat import format_tool_error
        
        error = format_tool_error(
            error_type="json_parse",
            tool_name="mcp_filesystem_read_file",
            details="Expecting property name at position 5"
        )
        
        assert "JSON" in error
        assert "mcp_filesystem_read_file" in error

    def test_format_invalid_tool_name_error(self):
        """Test formatting invalid tool name error."""
        from openrouter_cli.commands.chat import format_tool_error
        
        error = format_tool_error(
            error_type="invalid_tool_name",
            tool_name="mcp_filesystem",
            details="Expected format: mcp_{server}_{tool}"
        )
        
        assert "mcp_filesystem" in error
        assert "format" in error.lower()

    def test_format_execution_error(self):
        """Test formatting execution error."""
        from openrouter_cli.commands.chat import format_tool_error
        
        error = format_tool_error(
            error_type="execution",
            tool_name="mcp_filesystem_read_file",
            details="File not found: /nonexistent"
        )
        
        assert "File not found" in error

    def test_format_unknown_tool_error(self):
        """Test formatting unknown tool error."""
        from openrouter_cli.commands.chat import format_tool_error
        
        error = format_tool_error(
            error_type="unknown_tool",
            tool_name="mystery_function",
            details=None
        )
        
        assert "mystery_function" in error
        assert "unknown" in error.lower() or "not found" in error.lower()
