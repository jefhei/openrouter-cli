"""MCP (Model Context Protocol) command implementation."""

import json
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config import get_config_manager, MCPServerConfig
from ..utils.formatting import print_error, print_success, print_warning, print_info


console = Console()


def expand_path(path: str) -> str:
    """Expand ~ and environment variables in a path."""
    return str(Path(path).expanduser())


@click.group("mcp")
def mcp() -> None:
    """Manage MCP (Model Context Protocol) servers."""
    pass


@mcp.command("list")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_servers(output_json: bool) -> None:
    """List configured MCP servers."""
    config = get_config_manager()
    servers = config.config.mcp.servers

    if output_json:
        data = {name: srv.model_dump() for name, srv in servers.items()}
        console.print_json(data=data)
        return

    if not servers:
        console.print("[dim]No MCP servers configured[/dim]")
        console.print()
        console.print("To enable filesystem MCP:")
        console.print("  openrouter mcp enable filesystem ~/Documents")
        return

    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Enabled", justify="center")
    table.add_column("Command")
    table.add_column("Directories")

    for name, server in servers.items():
        enabled = "✓" if server.enabled else "✗"
        enabled_style = "green" if server.enabled else "red"
        dirs = ", ".join(server.allowed_directories) if server.allowed_directories else "-"
        if len(dirs) > 40:
            dirs = dirs[:37] + "..."

        table.add_row(
            name,
            f"[{enabled_style}]{enabled}[/{enabled_style}]",
            server.command,
            dirs,
        )

    console.print(table)


@mcp.command("enable")
@click.argument("server_name")
@click.argument("directories", nargs=-1)
@click.option("--command", default="npx", help="Command to run server")
@click.option("--args", "extra_args", multiple=True, help="Additional arguments")
def enable(server_name: str, directories: tuple[str, ...], command: str, extra_args: tuple[str, ...]) -> None:
    """Enable an MCP server.

    For filesystem server, specify allowed directories.

    Examples:
        openrouter mcp enable filesystem ~/Documents ~/Projects
        openrouter mcp enable filesystem .
    """
    config = get_config_manager()

    # Expand directory paths
    expanded_dirs = [expand_path(d) for d in directories]

    # Validate directories exist
    for d in expanded_dirs:
        if not Path(d).exists():
            print_warning(f"Directory does not exist: {d}")

    if server_name == "filesystem":
        # Default filesystem server configuration
        args = ["-y", "@modelcontextprotocol/server-filesystem"] + list(expanded_dirs)
        if extra_args:
            args.extend(extra_args)

        server_config = MCPServerConfig(
            enabled=True,
            command=command,
            args=args,
            allowed_directories=expanded_dirs,
        )
    else:
        # Generic server configuration
        args = list(extra_args) if extra_args else []
        server_config = MCPServerConfig(
            enabled=True,
            command=command,
            args=args,
            allowed_directories=list(expanded_dirs) if expanded_dirs else [],
        )

    # Update config
    servers = config.config.mcp.servers.copy()
    servers[server_name] = server_config
    config.set("mcp.servers", {name: srv.model_dump() for name, srv in servers.items()})

    print_success(f"Enabled MCP server '{server_name}'")
    if expanded_dirs:
        console.print(f"[dim]Allowed directories: {', '.join(expanded_dirs)}[/dim]")


@mcp.command("disable")
@click.argument("server_name")
def disable(server_name: str) -> None:
    """Disable an MCP server."""
    config = get_config_manager()
    servers = config.config.mcp.servers

    if server_name not in servers:
        print_error(f"Server '{server_name}' not found")
        raise SystemExit(1)

    servers[server_name].enabled = False
    config.set("mcp.servers", {name: srv.model_dump() for name, srv in servers.items()})

    print_success(f"Disabled MCP server '{server_name}'")


@mcp.command("status")
@click.argument("server_name", required=False)
def status(server_name: str | None) -> None:
    """Show MCP server status."""
    config = get_config_manager()
    servers = config.config.mcp.servers

    if not servers:
        console.print("[dim]No MCP servers configured[/dim]")
        return

    if server_name:
        if server_name not in servers:
            print_error(f"Server '{server_name}' not found")
            raise SystemExit(1)
        servers = {server_name: servers[server_name]}

    for name, server in servers.items():
        content = Text()
        content.append(f"Server: ", style="bold")
        content.append(f"{name}\n")
        content.append(f"Enabled: ", style="bold")
        status_style = "green" if server.enabled else "red"
        content.append(f"{server.enabled}\n", style=status_style)
        content.append(f"Command: ", style="bold")
        content.append(f"{server.command} {' '.join(server.args)}\n")

        if server.allowed_directories:
            content.append(f"\nAllowed Directories:\n", style="bold")
            for d in server.allowed_directories:
                exists = "✓" if Path(d).exists() else "✗"
                style = "green" if Path(d).exists() else "red"
                content.append(f"  [{style}]{exists}[/{style}] {d}\n")

        if server.allowed_tools:
            content.append(f"\nAllowed Tools: ", style="bold")
            content.append(f"{', '.join(server.allowed_tools)}\n")

        if server.blocked_tools:
            content.append(f"Blocked Tools: ", style="bold")
            content.append(f"{', '.join(server.blocked_tools)}\n")

        console.print(Panel(content, title=name, border_style="blue"))


@mcp.command("tools")
@click.argument("server_name")
@click.option("--refresh", is_flag=True, help="Refresh tool list from server")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def tools(server_name: str, refresh: bool, output_json: bool) -> None:
    """View available tools from an MCP server."""
    # Define known tools for common servers
    filesystem_tools = [
        {"name": "read_file", "description": "Read contents of a file"},
        {"name": "read_multiple_files", "description": "Read multiple files at once"},
        {"name": "write_file", "description": "Create or overwrite a file"},
        {"name": "edit_file", "description": "Make selective edits to a file"},
        {"name": "create_directory", "description": "Create a new directory"},
        {"name": "list_directory", "description": "List directory contents"},
        {"name": "directory_tree", "description": "Get recursive tree view"},
        {"name": "move_file", "description": "Move or rename files/directories"},
        {"name": "search_files", "description": "Search for files by pattern"},
        {"name": "get_file_info", "description": "Get file metadata"},
    ]

    known_tools = {
        "filesystem": filesystem_tools,
    }

    if server_name in known_tools:
        tool_list = known_tools[server_name]

        if output_json:
            console.print_json(data=tool_list)
        else:
            table = Table(title=f"Tools: {server_name}")
            table.add_column("Name", style="cyan")
            table.add_column("Description")

            for tool in tool_list:
                table.add_row(tool["name"], tool["description"])

            console.print(table)
    else:
        print_info(f"Tool list not available for '{server_name}'")
        print_info("Run the server and use --refresh to fetch tools dynamically")


@mcp.command("test")
@click.argument("server_name")
def test(server_name: str) -> None:
    """Test MCP server connection."""
    config = get_config_manager()
    servers = config.config.mcp.servers

    if server_name not in servers:
        print_error(f"Server '{server_name}' not found")
        raise SystemExit(1)

    server = servers[server_name]

    if not server.enabled:
        print_warning(f"Server '{server_name}' is disabled")

    console.print(f"[dim]Testing server: {server.command} {' '.join(server.args[:3])}...[/dim]")

    try:
        # Try to start the server briefly
        result = subprocess.run(
            [server.command, "--version"] if server.command in ["node", "npx", "python"] else [server.command, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            print_success(f"Server command '{server.command}' is available")
        else:
            print_warning(f"Server command returned non-zero exit code")

        # Check if npx package exists
        if server.command == "npx" and server.args:
            pkg_args = [a for a in server.args if not a.startswith("-")]
            if pkg_args:
                pkg = pkg_args[0]
                console.print(f"[dim]Package: {pkg}[/dim]")

    except FileNotFoundError:
        print_error(f"Command '{server.command}' not found")
        print_info("Make sure Node.js is installed: node --version")
        raise SystemExit(1)
    except subprocess.TimeoutExpired:
        print_warning("Command timed out")
    except Exception as e:
        print_error(f"Test failed: {e}")
        raise SystemExit(1)


@mcp.command("logs")
@click.argument("server_name")
@click.option("--level", type=click.Choice(["debug", "info", "warn", "error"]), default="info")
@click.option("--tail", is_flag=True, help="Follow log output")
def logs(server_name: str, level: str, tail: bool) -> None:
    """View MCP server logs.

    Note: Logs are only available when running in verbose mode.
    """
    config = get_config_manager()
    log_dir = config.DEFAULT_CONFIG_DIR / "logs"
    log_file = log_dir / f"mcp-{server_name}.log"

    if not log_file.exists():
        console.print(f"[dim]No logs found for '{server_name}'[/dim]")
        console.print()
        console.print("Logs are created when using MCP with --verbose flag:")
        console.print(f"  openrouter chat --mcp {server_name} --verbose \"Hello\"")
        return

    if tail:
        # Stream log file
        import subprocess
        subprocess.run(["tail", "-f", str(log_file)])
    else:
        # Show recent logs
        with open(log_file) as f:
            lines = f.readlines()[-50:]  # Last 50 lines

        for line in lines:
            console.print(line.rstrip())


@mcp.command("restart")
@click.argument("server_name")
def restart(server_name: str) -> None:
    """Restart an MCP server.

    Note: This is a placeholder - MCP servers are started per-request.
    """
    config = get_config_manager()
    servers = config.config.mcp.servers

    if server_name not in servers:
        print_error(f"Server '{server_name}' not found")
        raise SystemExit(1)

    print_info(f"MCP servers are started on-demand per chat session")
    print_info("No persistent server process to restart")
