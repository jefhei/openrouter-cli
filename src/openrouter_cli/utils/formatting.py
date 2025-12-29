"""Formatting utilities for CLI output."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..models import ModelInfo, GenerationStats, Conversation


console = Console()


def format_cost(cost: float) -> str:
    """Format a cost value in USD."""
    if cost < 0.01:
        return f"${cost:.6f}"
    elif cost < 1:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"


def format_tokens(tokens: int) -> str:
    """Format a token count."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    else:
        return str(tokens)


def format_context_length(length: int) -> str:
    """Format a context length."""
    if length >= 1_000_000:
        return f"{length // 1_000_000}M"
    elif length >= 1_000:
        return f"{length // 1_000}K"
    else:
        return str(length)


def format_model_info(model: ModelInfo, detailed: bool = False) -> Panel | Table:
    """Format model information for display."""
    if detailed:
        # Detailed panel view
        content = Text()
        content.append(f"ID: ", style="bold")
        content.append(f"{model.id}\n")
        content.append(f"Name: ", style="bold")
        content.append(f"{model.name}\n")

        if model.description:
            content.append(f"Description: ", style="bold")
            content.append(f"{model.description}\n")

        content.append(f"\nContext Length: ", style="bold")
        content.append(f"{format_context_length(model.context_length)} tokens\n")

        content.append(f"\nPricing:\n", style="bold")
        content.append(f"  Prompt: {format_cost(model.pricing.prompt)}/1K tokens\n")
        content.append(f"  Completion: {format_cost(model.pricing.completion)}/1K tokens\n")
        if model.pricing.image:
            content.append(f"  Image: {format_cost(model.pricing.image)}/image\n")

        if model.architecture:
            content.append(f"\nArchitecture:\n", style="bold")
            for key, value in model.architecture.items():
                content.append(f"  {key}: {value}\n")

        if model.top_provider:
            content.append(f"\nTop Provider:\n", style="bold")
            for key, value in model.top_provider.items():
                content.append(f"  {key}: {value}\n")

        return Panel(content, title=model.name, border_style="blue")
    else:
        # Simple table row format
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("ID", model.id)
        table.add_row("Name", model.name)
        table.add_row("Context", format_context_length(model.context_length))
        table.add_row("Prompt", f"{format_cost(model.pricing.prompt)}/1K")
        table.add_row("Completion", f"{format_cost(model.pricing.completion)}/1K")
        return table


def format_models_table(models: list[ModelInfo]) -> Table:
    """Format a list of models as a table."""
    table = Table(title="Available Models")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Context", justify="right")
    table.add_column("Prompt $/1K", justify="right")
    table.add_column("Completion $/1K", justify="right")

    for model in models:
        table.add_row(
            model.id,
            model.name[:40] + "..." if len(model.name) > 40 else model.name,
            format_context_length(model.context_length),
            format_cost(model.pricing.prompt),
            format_cost(model.pricing.completion),
        )

    return table


def format_generation_stats(stats: GenerationStats) -> Panel:
    """Format generation statistics."""
    content = Text()
    content.append(f"Generation ID: ", style="bold")
    content.append(f"{stats.id}\n")
    content.append(f"Model: ", style="bold")
    content.append(f"{stats.model}\n")
    content.append(f"\nTokens:\n", style="bold")
    content.append(f"  Prompt: {format_tokens(stats.tokens_prompt)}\n")
    content.append(f"  Completion: {format_tokens(stats.tokens_completion)}\n")
    content.append(f"  Total: {format_tokens(stats.tokens_prompt + stats.tokens_completion)}\n")
    content.append(f"\nCost: ", style="bold")
    content.append(f"{format_cost(stats.total_cost)}\n")

    if stats.generation_time:
        content.append(f"Generation Time: ", style="bold")
        content.append(f"{stats.generation_time:.0f}ms\n")

    return Panel(content, title="Generation Stats", border_style="green")


def format_conversation_list(conversations: list[Conversation]) -> Table:
    """Format a list of conversations as a table."""
    table = Table(title="Saved Conversations")
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Messages", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Updated", style="dim")

    for conv in conversations:
        table.add_row(
            conv.name,
            conv.model,
            str(len(conv.messages)),
            format_tokens(conv.total_tokens),
            format_cost(conv.total_cost),
            conv.updated_at.strftime("%Y-%m-%d %H:%M"),
        )

    return table


def format_conversation_history(conversation: Conversation) -> Panel:
    """Format conversation history for display."""
    content = Text()

    for i, msg in enumerate(conversation.messages):
        role_style = {
            "system": "yellow",
            "user": "green",
            "assistant": "blue",
            "tool": "magenta",
        }.get(msg.role, "white")

        content.append(f"[{msg.role.upper()}]", style=f"bold {role_style}")
        content.append("\n")

        if isinstance(msg.content, str):
            content.append(msg.content)
        else:
            content.append(str(msg.content))

        if i < len(conversation.messages) - 1:
            content.append("\n\n" + "─" * 40 + "\n\n")

    return Panel(
        content,
        title=f"Conversation: {conversation.name}",
        subtitle=f"Model: {conversation.model} | Messages: {len(conversation.messages)}",
        border_style="blue",
    )


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")
