"""Conversations command implementation."""

import json
from pathlib import Path

import click
from rich.console import Console

from ..config import ConfigManager, get_config_manager
from ..models import Conversation, Message
from ..utils.formatting import (
    format_conversation_history,
    format_conversation_list,
    print_error,
    print_success,
)


console = Console()


def get_conversations_dir() -> Path:
    """Get the conversations directory."""
    config = get_config_manager()
    return config.CONVERSATIONS_DIR


def load_conversation(name: str) -> Conversation | None:
    """Load a conversation by name."""
    conv_dir = get_conversations_dir()
    conv_file = conv_dir / f"{name}.json"

    if not conv_file.exists():
        return None

    try:
        with open(conv_file) as f:
            data = json.load(f)
        return Conversation.model_validate(data)
    except Exception as e:
        print_error(f"Failed to load conversation: {e}")
        return None


def save_conversation(conversation: Conversation) -> None:
    """Save a conversation."""
    conv_dir = get_conversations_dir()
    conv_dir.mkdir(parents=True, exist_ok=True)

    conv_file = conv_dir / f"{conversation.name}.json"

    with open(conv_file, "w") as f:
        json.dump(conversation.model_dump(mode="json"), f, indent=2, default=str)


def list_conversations() -> list[Conversation]:
    """List all saved conversations."""
    conv_dir = get_conversations_dir()

    if not conv_dir.exists():
        return []

    conversations = []
    for conv_file in conv_dir.glob("*.json"):
        try:
            with open(conv_file) as f:
                data = json.load(f)
            conversations.append(Conversation.model_validate(data))
        except Exception:
            continue

    # Sort by updated_at descending
    conversations.sort(key=lambda c: c.updated_at, reverse=True)
    return conversations


def delete_conversation(name: str) -> bool:
    """Delete a conversation by name."""
    conv_dir = get_conversations_dir()
    conv_file = conv_dir / f"{name}.json"

    if not conv_file.exists():
        return False

    conv_file.unlink()
    return True


@click.group("conversations")
def conversations() -> None:
    """Manage saved conversations."""
    pass


@conversations.command("list")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_cmd(output_json: bool) -> None:
    """List saved conversations."""
    convs = list_conversations()

    if not convs:
        console.print("[dim]No saved conversations[/dim]")
        return

    if output_json:
        data = [c.model_dump(mode="json") for c in convs]
        console.print_json(data=data)
    else:
        table = format_conversation_list(convs)
        console.print(table)


@conversations.command("show")
@click.argument("name")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def show(name: str, output_json: bool) -> None:
    """Display conversation history."""
    conv = load_conversation(name)

    if not conv:
        print_error(f"Conversation '{name}' not found")
        raise SystemExit(1)

    if output_json:
        console.print_json(data=conv.model_dump(mode="json"))
    else:
        panel = format_conversation_history(conv)
        console.print(panel)


@conversations.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete(name: str, yes: bool) -> None:
    """Delete a saved conversation."""
    if not yes:
        click.confirm(f"Delete conversation '{name}'?", abort=True)

    if delete_conversation(name):
        print_success(f"Deleted conversation '{name}'")
    else:
        print_error(f"Conversation '{name}' not found")
        raise SystemExit(1)


@conversations.command("export")
@click.argument("name")
@click.argument("output", type=click.Path())
@click.option("--format", "fmt", type=click.Choice(["json", "markdown"]), default="json")
def export(name: str, output: str, fmt: str) -> None:
    """Export a conversation to a file."""
    conv = load_conversation(name)

    if not conv:
        print_error(f"Conversation '{name}' not found")
        raise SystemExit(1)

    output_path = Path(output).expanduser()

    if fmt == "json":
        with open(output_path, "w") as f:
            json.dump(conv.model_dump(mode="json"), f, indent=2, default=str)
    else:
        # Markdown format
        with open(output_path, "w") as f:
            f.write(f"# Conversation: {conv.name}\n\n")
            f.write(f"Model: {conv.model}\n")
            f.write(f"Created: {conv.created_at}\n")
            f.write(f"Updated: {conv.updated_at}\n\n")
            f.write("---\n\n")

            for msg in conv.messages:
                role = msg.role.upper()
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                f.write(f"## {role}\n\n{content}\n\n")

    print_success(f"Exported to {output_path}")


@conversations.command("import")
@click.argument("input", type=click.Path(exists=True))
@click.option("--name", help="Override conversation name")
def import_conv(input: str, name: str | None) -> None:
    """Import a conversation from a JSON file."""
    input_path = Path(input).expanduser()

    try:
        with open(input_path) as f:
            data = json.load(f)

        conv = Conversation.model_validate(data)

        if name:
            conv.name = name
            conv.id = name

        save_conversation(conv)
        print_success(f"Imported conversation '{conv.name}'")

    except Exception as e:
        print_error(f"Failed to import: {e}")
        raise SystemExit(1)


@conversations.command("clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def clear(yes: bool) -> None:
    """Delete all saved conversations."""
    convs = list_conversations()

    if not convs:
        console.print("[dim]No conversations to delete[/dim]")
        return

    if not yes:
        click.confirm(f"Delete all {len(convs)} conversations?", abort=True)

    for conv in convs:
        delete_conversation(conv.name)

    print_success(f"Deleted {len(convs)} conversations")
