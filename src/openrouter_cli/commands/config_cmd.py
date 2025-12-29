"""Configuration command implementation."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
import toml

from ..config import get_config_manager
from ..utils.formatting import print_error, print_success


console = Console()


@click.group("config")
def config() -> None:
    """Manage CLI configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str) -> None:
    """Set a configuration value.

    KEY is in dot notation (e.g., 'defaults.model', 'auth.api_key').

    Examples:
        openrouter config set api_key sk-or-v1-...
        openrouter config set defaults.model anthropic/claude-sonnet-4
        openrouter config set defaults.temperature 0.7
    """
    config_manager = get_config_manager()

    # Handle common shortcuts
    if key == "api_key":
        key = "auth.api_key"
    elif key == "model":
        key = "defaults.model"

    # Convert value types
    if value.lower() == "true":
        typed_value: str | int | float | bool = True
    elif value.lower() == "false":
        typed_value = False
    elif value.replace(".", "").replace("-", "").isdigit():
        if "." in value:
            typed_value = float(value)
        else:
            typed_value = int(value)
    else:
        typed_value = value

    try:
        config_manager.set(key, typed_value)
        print_success(f"Set {key} = {typed_value}")
    except Exception as e:
        print_error(f"Failed to set configuration: {e}")
        raise SystemExit(1)


@config.command("get")
@click.argument("key")
def get_config(key: str) -> None:
    """Get a configuration value.

    KEY is in dot notation (e.g., 'defaults.model', 'auth.api_key').
    """
    config_manager = get_config_manager()

    # Handle common shortcuts
    if key == "api_key":
        key = "auth.api_key"
    elif key == "model":
        key = "defaults.model"

    value = config_manager.get(key)

    if value is None:
        console.print(f"[dim]{key} is not set[/dim]")
    elif key.endswith("api_key") and isinstance(value, str) and len(value) > 10:
        # Mask API key
        masked = value[:10] + "..." + value[-4:]
        console.print(f"{key} = {masked}")
    else:
        console.print(f"{key} = {value}")


@config.command("show")
@click.option("--reveal", is_flag=True, help="Show full API key (not masked)")
def show_config(reveal: bool) -> None:
    """Display all configuration."""
    config_manager = get_config_manager()
    config_dict = config_manager.config.model_dump(exclude_none=True)

    # Mask API key unless reveal is set
    if not reveal and "auth" in config_dict and "api_key" in config_dict["auth"]:
        api_key = config_dict["auth"]["api_key"]
        if api_key and len(api_key) > 10:
            config_dict["auth"]["api_key"] = api_key[:10] + "..." + api_key[-4:]

    # Format as TOML
    toml_str = toml.dumps(config_dict)
    syntax = Syntax(toml_str, "toml", theme="monokai", line_numbers=False)

    console.print(Panel(syntax, title=f"Configuration ({config_manager.config_path})", border_style="blue"))


@config.command("path")
def config_path() -> None:
    """Show the configuration file path."""
    config_manager = get_config_manager()
    console.print(str(config_manager.config_path))


@config.command("reset")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def reset_config(yes: bool) -> None:
    """Reset configuration to defaults."""
    if not yes:
        click.confirm("This will reset all configuration to defaults. Continue?", abort=True)

    config_manager = get_config_manager()

    # Remove config file
    if config_manager.config_path.exists():
        config_manager.config_path.unlink()

    # Reset cached config
    config_manager._config = None

    print_success("Configuration reset to defaults")


@config.command("edit")
def edit_config() -> None:
    """Open configuration file in default editor."""
    import os
    import subprocess

    config_manager = get_config_manager()
    config_path = config_manager.config_path

    # Ensure file exists
    if not config_path.exists():
        config_manager.save()

    # Get editor from environment
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"

    try:
        subprocess.run([editor, str(config_path)], check=True)
        print_success(f"Configuration saved to {config_path}")
    except FileNotFoundError:
        print_error(f"Editor '{editor}' not found. Set EDITOR environment variable.")
        raise SystemExit(1)
    except subprocess.CalledProcessError:
        print_error("Editor exited with error")
        raise SystemExit(1)
