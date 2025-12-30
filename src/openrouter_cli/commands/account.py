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
    client = None
    try:
        client = OpenRouterClient(api_key=api_key)
        account_balance = client.get_account_balance()
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(1)
    finally:
        if client is not None:
            client.close()

    # Handle None values from API (pay-as-you-go accounts)
    credits = account_balance.credits
    usage = account_balance.usage if account_balance.usage is not None else 0.0
    limit = getattr(account_balance, 'limit', None)

    if output_json:
        console.print_json(data={
            "credits": credits,
            "usage": usage,
            "limit": limit,
            "account_type": "pay_as_you_go" if limit is None else "prepaid",
        })
    else:
        content = Text()
        
        if credits is None or limit is None:
            # Pay-as-you-go account (no pre-purchased credits)
            content.append("Account Type: ", style="bold")
            content.append("Pay as you go\n", style="cyan")
            content.append("Total Usage: ", style="bold")
            content.append(f"{format_cost(usage)}", style="yellow")
        else:
            # Pre-paid credits account
            content.append("Available Credits: ", style="bold")
            if credits >= 0:
                content.append(f"{format_cost(credits)}\n", style="green")
            else:
                content.append(f"{format_cost(credits)}\n", style="red")
            content.append("Credit Limit: ", style="bold")
            content.append(f"{format_cost(limit)}\n", style="dim")
            content.append("Total Usage: ", style="bold")
            content.append(f"{format_cost(usage)}", style="yellow")

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
    client = None
    try:
        client = OpenRouterClient(api_key=api_key)
        account_balance = client.get_account_balance()
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(1)
    finally:
        if client is not None:
            client.close()

    # Handle None values from API
    credits = account_balance.credits
    usage_amount = account_balance.usage if account_balance.usage is not None else 0.0
    limit = getattr(account_balance, 'limit', None)

    if output_json:
        console.print_json(data={
            "period": period,
            "total_usage": usage_amount,
            "remaining_credits": credits,
            "limit": limit,
            "account_type": "pay_as_you_go" if limit is None else "prepaid",
        })
    else:
        table = Table(title=f"Usage Summary ({period})")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Total Usage", format_cost(usage_amount))
        
        if credits is None or limit is None:
            table.add_row("Account Type", "Pay as you go")
        else:
            table.add_row("Remaining Credits", format_cost(credits))
            table.add_row("Credit Limit", format_cost(limit))

        console.print(table)
        console.print()
        console.print("[dim]For detailed usage breakdown, visit:[/dim]")
        console.print("[link=https://openrouter.ai/activity]https://openrouter.ai/activity[/link]")