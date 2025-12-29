"""Chat command implementation."""

import base64
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.prompt import Prompt

from ..client import OpenRouterClient, OpenRouterError
from ..config import get_config_manager
from ..models import Message
from ..utils.streaming import create_printer
from ..utils.formatting import format_cost, print_error, print_info
from .conversations import load_conversation, save_conversation


console = Console()


def read_image_as_base64(path: str) -> tuple[str, str]:
    """Read an image file and return base64 data and media type."""
    p = Path(path).expanduser()
    if not p.exists():
        raise click.ClickException(f"Image file not found: {path}")

    suffix = p.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    if suffix not in media_types:
        raise click.ClickException(f"Unsupported image format: {suffix}")

    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return data, media_types[suffix]


def build_message_content(
    text: str,
    images: tuple[str, ...] | None = None,
    image_urls: tuple[str, ...] | None = None,
) -> str | list[dict[str, Any]]:
    """Build message content, optionally with images."""
    if not images and not image_urls:
        return text

    content: list[dict[str, Any]] = []

    # Add images from files
    if images:
        for img_path in images:
            data, media_type = read_image_as_base64(img_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{data}"
                }
            })

    # Add images from URLs
    if image_urls:
        for url in image_urls:
            content.append({
                "type": "image_url",
                "image_url": {"url": url}
            })

    # Add text
    if text:
        content.append({"type": "text", "text": text})

    return content


def load_tools(tools_file: str | None, tool_defs: tuple[str, ...] | None) -> list[dict[str, Any]] | None:
    """Load tool definitions from file or inline."""
    tools: list[dict[str, Any]] = []

    if tools_file:
        p = Path(tools_file).expanduser()
        if not p.exists():
            raise click.ClickException(f"Tools file not found: {tools_file}")
        with open(p) as f:
            data = json.load(f)
            if isinstance(data, list):
                tools.extend(data)
            else:
                tools.append(data)

    if tool_defs:
        for tool_json in tool_defs:
            try:
                tool = json.loads(tool_json)
                if "type" not in tool:
                    tool = {"type": "function", "function": tool}
                tools.append(tool)
            except json.JSONDecodeError as e:
                raise click.ClickException(f"Invalid tool JSON: {e}")

    return tools if tools else None


@click.command("chat")
@click.argument("prompt", required=False)
@click.option("-m", "--model", help="Model to use for completion")
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key")
@click.option("-t", "--temperature", type=float, help="Sampling temperature (0-2)")
@click.option("--max-tokens", type=int, help="Maximum tokens to generate")
@click.option("--top-p", type=float, help="Top-p sampling parameter")
@click.option("--top-k", type=int, help="Top-k sampling parameter")
@click.option("--frequency-penalty", type=float, help="Frequency penalty (-2 to 2)")
@click.option("--presence-penalty", type=float, help="Presence penalty (-2 to 2)")
@click.option("--stop", multiple=True, help="Stop sequences (can be repeated)")
@click.option("-s", "--system", help="System prompt")
@click.option("--no-stream", is_flag=True, help="Disable streaming")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON response")
@click.option("--json-mode", is_flag=True, help="Request JSON output from model")
@click.option("-q", "--quiet", is_flag=True, help="Only output the response text")
@click.option("-v", "--verbose", is_flag=True, help="Show request/response details")
@click.option("--dry-run", is_flag=True, help="Estimate cost without sending")
@click.option("--show-cost", is_flag=True, help="Show cost after response")
@click.option("-c", "--conversation", help="Named conversation to continue")
@click.option("-i", "--interactive", is_flag=True, help="Interactive mode")
@click.option("--image", multiple=True, help="Image file path (can be repeated)")
@click.option("--image-url", multiple=True, help="Image URL (can be repeated)")
@click.option("--tools", "tools_file", help="JSON file with tool definitions")
@click.option("--tool", "tool_defs", multiple=True, help="Inline tool definition JSON")
@click.option("--provider", multiple=True, help="Preferred providers")
@click.option("--exclude-provider", multiple=True, help="Excluded providers")
@click.option("--require-params", help="Required parameter support (comma-separated)")
@click.option("--mcp", multiple=True, help="MCP servers to enable")
@click.option("--mcp-allow", help="Allowed MCP tools (comma-separated)")
@click.option("--mcp-block", help="Blocked MCP tools (comma-separated)")
@click.option("--mcp-readonly", is_flag=True, help="Read-only MCP mode")
def chat(
    prompt: str | None,
    model: str | None,
    api_key: str | None,
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
    top_k: int | None,
    frequency_penalty: float | None,
    presence_penalty: float | None,
    stop: tuple[str, ...],
    system: str | None,
    no_stream: bool,
    output_json: bool,
    json_mode: bool,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
    show_cost: bool,
    conversation: str | None,
    interactive: bool,
    image: tuple[str, ...],
    image_url: tuple[str, ...],
    tools_file: str | None,
    tool_defs: tuple[str, ...],
    provider: tuple[str, ...],
    exclude_provider: tuple[str, ...],
    require_params: str | None,
    mcp: tuple[str, ...],
    mcp_allow: str | None,
    mcp_block: str | None,
    mcp_readonly: bool,
) -> None:
    """Send a chat completion request.

    PROMPT can be a text prompt, or '-' to read from stdin.
    If no prompt is provided, enters interactive mode.
    """
    config = get_config_manager()

    # Handle stdin input
    if prompt == "-":
        prompt = sys.stdin.read().strip()
    elif prompt is None and not interactive and not sys.stdin.isatty():
        # Read from pipe
        prompt = sys.stdin.read().strip()

    # Enter interactive mode if no prompt and terminal
    if not prompt and not interactive:
        interactive = True

    # Load tools
    tools = load_tools(tools_file, tool_defs)

    # Build provider preferences
    provider_config: dict[str, Any] | None = None
    if provider or exclude_provider or require_params:
        provider_config = {}
        if provider:
            provider_config["order"] = list(provider)
        if exclude_provider:
            provider_config["ignore"] = list(exclude_provider)
        if require_params:
            provider_config["require_parameters"] = True

    # Response format for JSON mode
    response_format = {"type": "json_object"} if json_mode else None

    try:
        client = OpenRouterClient(api_key=api_key)
    except OpenRouterError as e:
        print_error(str(e))
        raise SystemExit(3)

    # Load or create conversation
    messages: list[dict[str, Any]] = []
    conv = None

    if conversation:
        conv = load_conversation(conversation)
        if conv:
            messages = [m.model_dump(exclude_none=True) for m in conv.messages]
            if not quiet:
                print_info(f"Continuing conversation '{conversation}' ({len(messages)} messages)")

    # Add system prompt
    if system and not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": system})

    def send_message(user_prompt: str) -> str | None:
        """Send a message and return the response."""
        nonlocal messages

        # Build user message content
        content = build_message_content(user_prompt, image, image_url)
        messages.append({"role": "user", "content": content})

        if dry_run:
            # Estimate tokens (rough approximation)
            text_content = user_prompt
            for m in messages:
                c = m.get("content", "")
                if isinstance(c, str):
                    text_content += c
            estimated_tokens = len(text_content) // 4
            print_info(f"Estimated prompt tokens: ~{estimated_tokens}")
            print_info("(Dry run - request not sent)")
            return None

        if verbose:
            console.print("[dim]Request:[/dim]")
            console.print_json(data={"messages": messages, "model": model or config.config.defaults.model})

        stream = not no_stream and not output_json
        printer = create_printer(quiet=quiet, plain=output_json)

        try:
            if stream:
                printer.start()
                full_response = ""
                model_used = ""
                generation_id = ""

                for chunk in client.chat_completion_stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    top_k=top_k,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    stop=list(stop) if stop else None,
                    tools=tools,
                    response_format=response_format,
                    provider=provider_config,
                ):
                    if not model_used:
                        model_used = chunk.model
                    if not generation_id:
                        generation_id = chunk.id

                    for choice in chunk.choices:
                        if choice.delta.content:
                            printer.write(choice.delta.content)
                            full_response += choice.delta.content

                printer.finish()

                if show_cost and generation_id:
                    try:
                        stats = client.get_generation_stats(generation_id)
                        printer.print_metadata(
                            model=model_used,
                            cost=stats.total_cost,
                            tokens={
                                "prompt": stats.tokens_prompt,
                                "completion": stats.tokens_completion,
                                "total": stats.tokens_prompt + stats.tokens_completion,
                            },
                        )
                    except Exception:
                        pass

                # Add assistant response to messages
                messages.append({"role": "assistant", "content": full_response})
                return full_response

            else:
                # Non-streaming
                response = client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    top_k=top_k,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    stop=list(stop) if stop else None,
                    tools=tools,
                    response_format=response_format,
                    provider=provider_config,
                )

                if output_json:
                    console.print_json(data=response.model_dump())
                else:
                    content = response.choices[0].message.content
                    if isinstance(content, str):
                        console.print(content)

                if show_cost and response.usage:
                    printer.print_metadata(
                        model=response.model,
                        tokens={
                            "prompt": response.usage.prompt_tokens,
                            "completion": response.usage.completion_tokens,
                            "total": response.usage.total_tokens,
                        },
                    )

                # Add assistant response to messages
                assistant_content = response.choices[0].message.content
                messages.append({"role": "assistant", "content": assistant_content})

                if isinstance(assistant_content, str):
                    return assistant_content
                return str(assistant_content)

        except OpenRouterError as e:
            print_error(str(e))
            if e.status_code == 401:
                raise SystemExit(3)
            elif e.status_code == 429:
                raise SystemExit(4)
            elif e.status_code == 404:
                raise SystemExit(5)
            elif e.status_code == 402:
                raise SystemExit(6)
            else:
                raise SystemExit(1)

    try:
        if interactive:
            # Interactive mode
            console.print("[bold blue]OpenRouter Chat[/bold blue] (type 'exit' or Ctrl+D to quit)")
            console.print(f"[dim]Model: {model or config.config.defaults.model}[/dim]")
            console.print()

            while True:
                try:
                    user_input = Prompt.ask("[bold green]You[/bold green]")
                    if user_input.lower() in ("exit", "quit", "q"):
                        break
                    if not user_input.strip():
                        continue

                    console.print()
                    send_message(user_input)
                    console.print()

                except EOFError:
                    break
                except KeyboardInterrupt:
                    console.print("\n[dim]Interrupted[/dim]")
                    break

        elif prompt:
            send_message(prompt)

        # Save conversation if named
        if conversation and messages:
            from ..models import Conversation, Message as MsgModel

            if conv is None:
                conv = Conversation(
                    id=conversation,
                    name=conversation,
                    model=model or config.config.defaults.model,
                )

            conv.messages = [MsgModel.model_validate(m) for m in messages]
            save_conversation(conv)
            if not quiet:
                print_info(f"Conversation saved as '{conversation}'")

    finally:
        client.close()


@click.command("chat")
@click.pass_context
def chat_command(ctx: click.Context) -> None:
    """Send a chat completion request."""
    ctx.invoke(chat)
