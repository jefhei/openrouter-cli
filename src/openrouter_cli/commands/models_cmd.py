"""Models command implementation."""

import json

import click
from rich.console import Console
from rich.table import Table

from ..client import OpenRouterClient, OpenRouterError
from ..models import ModelInfo
from ..utils.formatting import (
    format_context_length,
    format_cost,
    format_model_info,
    print_error,
)


console = Console()


@click.group("models")
def models() -> None:
    """Manage and explore available models."""
    pass


@models.command("list")
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key")
@click.option("--sort", "sort_by", type=click.Choice(["name", "price", "context"]), help="Sort by field")
@click.option("--min-context", type=int, help="Minimum context length")
@click.option("--max-price", type=float, help="Maximum price per 1K tokens (prompt)")
@click.option("--provider", help="Filter by provider")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("-n", "--limit", type=int, help="Limit number of results")
def list_models(
    api_key: str | None,
    sort_by: str | None,
    min_context: int | None,
    max_price: float | None,
    provider: str | None,
    output_json: bool,
    limit: int | None,
) -> None:
    """List all available models."""
    try:
        client = OpenRouterClient(api_key=api_key)
        models_list = client.list_models()
        client.close()
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(1)

    # Filter models
    if min_context:
        models_list = [m for m in models_list if m.context_length >= min_context]

    if max_price:
        models_list = [m for m in models_list if m.pricing.prompt <= max_price]

    if provider:
        provider_lower = provider.lower()
        models_list = [m for m in models_list if provider_lower in m.author.lower()]

    # Sort models
    if sort_by == "name":
        models_list.sort(key=lambda m: m.name.lower())
    elif sort_by == "price":
        models_list.sort(key=lambda m: m.pricing.prompt)
    elif sort_by == "context":
        models_list.sort(key=lambda m: m.context_length, reverse=True)

    # Limit results
    if limit:
        models_list = models_list[:limit]

    if output_json:
        data = [m.model_dump() for m in models_list]
        console.print_json(data=data)
    else:
        table = Table(title=f"Available Models ({len(models_list)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Context", justify="right")
        table.add_column("Prompt $/1K", justify="right")
        table.add_column("Completion $/1K", justify="right")

        for model in models_list:
            name = model.name
            if len(name) > 45:
                name = name[:42] + "..."
            table.add_row(
                model.id,
                name,
                format_context_length(model.context_length),
                format_cost(model.pricing.prompt),
                format_cost(model.pricing.completion),
            )

        console.print(table)


@models.command("search")
@click.argument("query", required=False)
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key")
@click.option("--provider", help="Filter by provider name")
@click.option("--min-context", type=int, help="Minimum context length")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def search_models(
    query: str | None,
    api_key: str | None,
    provider: str | None,
    min_context: int | None,
    output_json: bool,
) -> None:
    """Search for models by name or provider."""
    try:
        client = OpenRouterClient(api_key=api_key)
        models_list = client.list_models()
        client.close()
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(1)

    # Filter by query
    if query:
        query_lower = query.lower()
        models_list = [
            m for m in models_list
            if query_lower in m.id.lower()
            or query_lower in m.name.lower()
            or (m.description and query_lower in m.description.lower())
        ]

    # Filter by provider
    if provider:
        provider_lower = provider.lower()
        models_list = [m for m in models_list if provider_lower in m.author.lower()]

    # Filter by context
    if min_context:
        models_list = [m for m in models_list if m.context_length >= min_context]

    if not models_list:
        console.print("[yellow]No models found matching your criteria[/yellow]")
        return

    if output_json:
        data = [m.model_dump() for m in models_list]
        console.print_json(data=data)
    else:
        table = Table(title=f"Search Results ({len(models_list)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Context", justify="right")
        table.add_column("Prompt $/1K", justify="right")

        for model in models_list:
            name = model.name
            if len(name) > 45:
                name = name[:42] + "..."
            table.add_row(
                model.id,
                name,
                format_context_length(model.context_length),
                format_cost(model.pricing.prompt),
            )

        console.print(table)


@models.command("info")
@click.argument("model_id")
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def model_info(model_id: str, api_key: str | None, output_json: bool) -> None:
    """Get detailed information about a specific model."""
    try:
        client = OpenRouterClient(api_key=api_key)
        model = client.get_model(model_id)
        client.close()
    except OpenRouterError as e:
        print_error(str(e))
        if "not found" in str(e).lower():
            raise SystemExit(5)
        raise SystemExit(1)

    if output_json:
        console.print_json(data=model.model_dump())
    else:
        panel = format_model_info(model, detailed=True)
        console.print(panel)
