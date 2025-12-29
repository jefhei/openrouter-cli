"""Account command implementation."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..client import OpenRouterClient, OpenRouterError
from ..utils.formatting import format_cost, print_error


console = Console()


@click.group("account")
def account() -> None:
    """Manage account and billing."""
    pass


@account.command("balance")
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def balance(api_key: str | None, output_json: bool) -> None:
    """Check account credit balance."""
    try:
        client = OpenRouterClient(api_key=api_key)
        account_balance = client.get_account_balance()
        client.close()
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(1)

    if output_json:
        console.print_json(data={
            "credits": account_balance.credits,
            "usage": account_balance.usage,
        })
    else:
        content = Text()
        content.append("Available Credits: ", style="bold")
        content.append(f"{format_cost(account_balance.credits)}\n", style="green")
        content.append("Total Usage: ", style="bold")
        content.append(f"{format_cost(account_balance.usage)}", style="yellow")

        panel = Panel(content, title="Account Balance", border_style="blue")
        console.print(panel)


@account.command("usage")
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key")
@click.option("--period", type=click.Choice(["day", "week", "month"]), default="month", help="Time period")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def usage(api_key: str | None, period: str, output_json: bool) -> None:
    """View usage statistics.

    Note: Detailed usage statistics require the OpenRouter dashboard.
    This command shows available balance information.
    """
    try:
        client = OpenRouterClient(api_key=api_key)
        account_balance = client.get_account_balance()
        client.close()
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(1)

    if output_json:
        console.print_json(data={
            "period": period,
            "total_usage": account_balance.usage,
            "remaining_credits": account_balance.credits,
        })
    else:
        table = Table(title=f"Usage Summary ({period})")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Total Usage", format_cost(account_balance.usage))
        table.add_row("Remaining Credits", format_cost(account_balance.credits))

        console.print(table)
        console.print()
        console.print("[dim]For detailed usage breakdown, visit:[/dim]")
        console.print("[link=https://openrouter.ai/activity]https://openrouter.ai/activity[/link]")
