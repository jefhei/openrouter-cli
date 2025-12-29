"""MCP server manager with full JSON-RPC protocol support."""

import json
import os
import subprocess
import threading
import queue
from pathlib import Path
from typing import Any

from ..config import get_config_manager, MCPServerConfig
from ..models import MCPTool


class MCPServerError(Exception):
    """MCP server error."""
    pass


class MCPServerConnection:
    """Manages a connection to a single MCP server."""

    def __init__(self, name: str, config: MCPServerConfig):
        self.name = name
        self.config = config
        self.process: subprocess.Popen | None = None
        self._request_id = 0
        self._response_queue: queue.Queue = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self._tools: list[MCPTool] = []
        self._initialized = False

    def start(self) -> None:
        """Start the MCP server process."""
        if self.process is not None:
            return

        # Build environment with config env vars
        env = os.environ.copy()
        if self.config.env:
            for key, value in self.config.env.items():
                # Expand environment variables in values
                if value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    value = os.environ.get(env_var, "")
                env[key] = value

        # Start the process
        try:
            self.process = subprocess.Popen(
                [self.config.command] + list(self.config.args),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,  # Line buffered
            )
        except Exception as e:
            raise MCPServerError(f"Failed to start server '{self.name}': {e}")

        # Start reader thread
        self._running = True
        self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._reader_thread.start()

        # Initialize the connection
        self._initialize()

    def _read_responses(self) -> None:
        """Background thread to read responses from the server."""
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                    # Only queue responses (messages with "id" field)
                    # Notifications (no id) are logged but not queued
                    if "id" in message:
                        self._response_queue.put(message)
                except json.JSONDecodeError:
                    pass  # Ignore non-JSON output
            except Exception:
                break

    def _send_request(self, method: str, params: dict | None = None, timeout: float = 30.0) -> Any:
        """Send a JSON-RPC request and wait for response."""
        if not self.process or not self.process.stdin:
            raise MCPServerError(f"Server '{self.name}' is not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        # Send request
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
        except Exception as e:
            raise MCPServerError(f"Failed to send request to '{self.name}': {e}")

        # Wait for response with matching ID
        try:
            while True:
                response = self._response_queue.get(timeout=timeout)
                if response.get("id") == self._request_id:
                    if "error" in response:
                        error = response["error"]
                        raise MCPServerError(
                            f"Server error: {error.get('message', 'Unknown error')}"
                        )
                    return response.get("result")
        except queue.Empty:
            raise MCPServerError(f"Timeout waiting for response from '{self.name}'")

    def _initialize(self) -> None:
        """Initialize the MCP connection."""
        if self._initialized:
            return

        # Send initialize request
        result = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "clientInfo": {
                "name": "openrouter-cli",
                "version": "1.0.0",
            },
        })

        # Send initialized notification (no response expected)
        if self.process and self.process.stdin:
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            self.process.stdin.write(json.dumps(notification) + "\n")
            self.process.stdin.flush()

        self._initialized = True

    def list_tools(self) -> list[MCPTool]:
        """Fetch available tools from the server."""
        if not self._initialized:
            self.start()

        result = self._send_request("tools/list", {})
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
            ))
        self._tools = tools
        return tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the server."""
        if not self._initialized:
            self.start()

        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        # Extract content from result
        content_parts = []
        for content in result.get("content", []):
            if content.get("type") == "text":
                content_parts.append(content.get("text", ""))
            elif content.get("type") == "image":
                content_parts.append(f"[Image: {content.get('mimeType', 'unknown')}]")
            elif content.get("type") == "resource":
                content_parts.append(f"[Resource: {content.get('uri', 'unknown')}]")
            else:
                content_parts.append(str(content))

        return "\n".join(content_parts)

    def stop(self) -> None:
        """Stop the server process."""
        self._running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None
        self._initialized = False


class MCPManager:
    """Manages MCP server connections and tool execution."""

    def __init__(self):
        self.config = get_config_manager()
        self._connections: dict[str, MCPServerConnection] = {}

    def get_server_config(self, name: str) -> MCPServerConfig | None:
        """Get configuration for a server."""
        return self.config.config.mcp.servers.get(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a server is enabled."""
        server = self.get_server_config(name)
        return server is not None and server.enabled

    def _get_connection(self, server_name: str) -> MCPServerConnection:
        """Get or create a connection to a server."""
        if server_name not in self._connections:
            config = self.get_server_config(server_name)
            if not config:
                raise MCPServerError(f"Server '{server_name}' not configured")
            if not config.enabled:
                raise MCPServerError(f"Server '{server_name}' is not enabled")
            self._connections[server_name] = MCPServerConnection(server_name, config)
        return self._connections[server_name]

    def get_tools(self, server_name: str) -> list[MCPTool]:
        """Get available tools from a server."""
        connection = self._get_connection(server_name)
        connection.start()
        return connection.list_tools()

    def get_tools_as_openai_format(
        self,
        server_names: list[str],
        allowed_tools: list[str] | None = None,
        blocked_tools: list[str] | None = None,
        readonly: bool = False,
    ) -> list[dict[str, Any]]:
        """Get tools in OpenAI function calling format."""
        # Common write operation tool names
        write_tools = {
            "write_file", "edit_file", "create_directory", "move_file",
            "create_repository", "create_branch", "create_or_update_file",
            "create_pull_request", "create_issue", "push_files", "delete_file",
            "fork_repository", "merge_pull_request", "update_pull_request",
        }

        tools = []
        for server_name in server_names:
            try:
                server_config = self.get_server_config(server_name)
                mcp_tools = self.get_tools(server_name)

                for tool in mcp_tools:
                    # Check server-level allowed/blocked lists
                    if server_config:
                        if server_config.allowed_tools and tool.name not in server_config.allowed_tools:
                            continue
                        if server_config.blocked_tools and tool.name in server_config.blocked_tools:
                            continue

                    # Check request-level allowed/blocked lists
                    if allowed_tools and tool.name not in allowed_tools:
                        continue
                    if blocked_tools and tool.name in blocked_tools:
                        continue
                    if readonly and tool.name in write_tools:
                        continue

                    tools.append({
                        "type": "function",
                        "function": {
                            "name": f"mcp_{server_name}_{tool.name}",
                            "description": tool.description,
                            "parameters": tool.input_schema,
                        }
                    })
            except MCPServerError as e:
                # Log error but continue with other servers
                print(f"Warning: Failed to get tools from '{server_name}': {e}")

        return tools

    def execute_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Execute an MCP tool and return the result."""
        connection = self._get_connection(server_name)
        connection.start()
        return connection.call_tool(tool_name, arguments)

    def close(self) -> None:
        """Close all server connections."""
        for connection in self._connections.values():
            connection.stop()
        self._connections.clear()
