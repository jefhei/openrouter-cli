"""OpenRouter CLI - Main entry point."""

import sys

import click
from rich.console import Console

from . import __version__
from .commands.chat import chat
from .commands.models_cmd import models
from .commands.config_cmd import config
from .commands.account import account
from .commands.conversations import conversations
from .commands.mcp_cmd import mcp


console = Console()


@click.group(invoke_without_command=True)
@click.option("--version", "-V", is_flag=True, help="Show version and exit")
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    """OpenRouter CLI - Access 400+ AI models from the command line.

    \b
    Examples:
        openrouter chat "Hello, how are you?"
        openrouter chat -m anthropic/claude-sonnet-4 "Explain quantum computing"
        openrouter models list
        openrouter config set api_key sk-or-v1-...

    For more information, visit: https://openrouter.ai/docs
    """
    if version:
        console.print(f"openrouter-cli {__version__}")
        raise SystemExit(0)

    if ctx.invoked_subcommand is None:
        # Show help if no command provided
        console.print(ctx.get_help())


@cli.command("version")
def version_cmd() -> None:
    """Show CLI version."""
    console.print(f"openrouter-cli {__version__}")


# Register command groups
cli.add_command(chat)
cli.add_command(models)
cli.add_command(config)
cli.add_command(account)
cli.add_command(conversations)
cli.add_command(mcp)


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
        sys.exit(130)
    except Exception as e:
        if "--verbose" in sys.argv or "-v" in sys.argv:
            raise
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
