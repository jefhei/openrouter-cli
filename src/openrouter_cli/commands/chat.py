"""Chat command implementation."""

import base64
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.prompt import Prompt

from ..client import OpenRouterClient, OpenRouterError
from ..config import get_config_manager
from ..mcp.manager import MCPManager, MCPServerError
from ..models import Message
from ..utils.streaming import create_printer
from ..utils.formatting import format_cost, print_error, print_info
from .conversations import load_conversation, save_conversation


@dataclass
class MessageStats:
    """Statistics from a single message exchange."""
    
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


console = Console()


def parse_tool_call(tool_call: dict) -> dict:
    """Parse a tool call dict and extract components with error handling.
    
    Args:
        tool_call: The tool call dictionary from the API response.
        
    Returns:
        A dict with keys: id, name, arguments, error
        - id: The tool call ID (empty string if missing)
        - name: The function name (empty string if missing)
        - arguments: Parsed arguments dict (empty dict if parsing fails)
        - error: Error message if any issue occurred, None otherwise
    """
    result = {
        "id": "",
        "name": "",
        "arguments": {},
        "error": None,
    }
    
    # Extract ID (optional, default to empty string)
    result["id"] = tool_call.get("id", "")
    
    # Extract function data
    func_data = tool_call.get("function")
    if func_data is None:
        result["error"] = "Tool call missing 'function' field"
        return result
    
    if not isinstance(func_data, dict):
        result["error"] = "Tool call 'function' field is not a dictionary"
        return result
    
    # Extract function name
    func_name = func_data.get("name")
    if not func_name:
        result["error"] = "Tool call missing function 'name' field"
        return result
    result["name"] = func_name
    
    # Extract and parse arguments
    func_args = func_data.get("arguments", "{}")
    
    if func_args is None or func_args == "":
        result["arguments"] = {}
    elif isinstance(func_args, dict):
        result["arguments"] = func_args
    elif isinstance(func_args, str):
        try:
            result["arguments"] = json.loads(func_args)
        except json.JSONDecodeError as e:
            result["arguments"] = {}
            result["error"] = f"Failed to parse tool arguments as JSON: {e}"
    else:
        result["arguments"] = {}
        result["error"] = f"Tool arguments has unexpected type: {type(func_args).__name__}"
    
    return result


def parse_mcp_tool_name(func_name: str) -> dict:
    """Parse an MCP tool name and extract server and tool components.
    
    MCP tool names follow the format: mcp_{server}_{tool}
    where {tool} may contain underscores.
    
    Args:
        func_name: The full function name from the tool call.
        
    Returns:
        A dict with keys: server_name, tool_name, error
        - server_name: The MCP server name (empty string if invalid)
        - tool_name: The tool name (empty string if invalid)  
        - error: Error message if format is invalid, None otherwise
    """
    result = {
        "server_name": "",
        "tool_name": "",
        "error": None,
    }
    
    if not func_name:
        result["error"] = "Tool name is empty"
        return result
    
    if not func_name.startswith("mcp_"):
        result["error"] = f"Tool '{func_name}' is not an MCP tool (must start with 'mcp_')"
        return result
    
    # Split into parts: mcp, server, tool (where tool may have underscores)
    parts = func_name.split("_", 2)
    
    if len(parts) < 3:
        result["error"] = (
            f"Invalid MCP tool name format: '{func_name}'. "
            f"Expected format: mcp_{{server}}_{{tool}}"
        )
        return result
    
    server_name = parts[1]
    tool_name = parts[2]
    
    if not server_name:
        result["error"] = f"MCP tool name '{func_name}' has empty server name"
        return result
    
    if not tool_name:
        result["error"] = f"MCP tool name '{func_name}' has empty tool name"
        return result
    
    result["server_name"] = server_name
    result["tool_name"] = tool_name
    return result


def execute_tool_call(
    func_name: str,
    args: dict,
    mcp_manager: "MCPManager | None",
) -> dict:
    """Execute a tool call with comprehensive error handling.
    
    Args:
        func_name: The function name to execute.
        args: The arguments to pass to the function.
        mcp_manager: The MCP manager instance (may be None).
        
    Returns:
        A dict with keys: success, result, error
        - success: True if execution succeeded
        - result: The result string from the tool (empty if failed)
        - error: Error message if execution failed, None otherwise
    """
    result = {
        "success": False,
        "result": "",
        "error": None,
    }
    
    # Check if this is an MCP tool
    if func_name.startswith("mcp_"):
        # Validate MCP manager is available
        if mcp_manager is None:
            result["error"] = (
                f"Cannot execute MCP tool '{func_name}': MCP is not enabled. "
                f"Use --mcp <server> to enable MCP tools."
            )
            return result
        
        # Parse the MCP tool name
        parsed = parse_mcp_tool_name(func_name)
        if parsed["error"]:
            result["error"] = parsed["error"]
            return result
        
        server_name = parsed["server_name"]
        tool_name = parsed["tool_name"]
        
        # Execute the tool
        try:
            tool_result = mcp_manager.execute_tool(server_name, tool_name, args)
            result["success"] = True
            result["result"] = tool_result
        except MCPServerError as e:
            result["error"] = f"MCP server error ({server_name}): {e}"
        except Exception as e:
            result["error"] = f"Unexpected error executing tool '{func_name}': {e}"
    else:
        # Non-MCP tool - not supported in this context
        result["error"] = (
            f"Unknown tool: '{func_name}'. "
            f"Only MCP tools (mcp_*) are supported when using --mcp."
        )
    
    return result


def format_tool_error(error_type: str, tool_name: str, details: str | None = None) -> str:
    """Format a tool error message for display and sending back to the model.
    
    Args:
        error_type: Type of error (json_parse, invalid_tool_name, execution, unknown_tool)
        tool_name: The name of the tool that failed
        details: Additional error details
        
    Returns:
        A formatted error message string
    """
    messages = {
        "json_parse": f"Error: Failed to parse JSON arguments for tool '{tool_name}'",
        "invalid_tool_name": f"Error: Invalid tool name format '{tool_name}'",
        "execution": f"Error executing tool '{tool_name}'",
        "unknown_tool": f"Error: Unknown tool '{tool_name}'",
    }
    
    base_message = messages.get(error_type, f"Error with tool '{tool_name}'")
    
    if details:
        return f"{base_message}: {details}"
    return base_message


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

    # Load MCP tools
    mcp_manager = None
    if mcp:
        mcp_manager = MCPManager()
        allowed = mcp_allow.split(",") if mcp_allow else None
        blocked = mcp_block.split(",") if mcp_block else None
        mcp_tools = mcp_manager.get_tools_as_openai_format(
            server_names=list(mcp),
            allowed_tools=allowed,
            blocked_tools=blocked,
            readonly=mcp_readonly,
        )
        if mcp_tools:
            tools = (tools or []) + mcp_tools
            if not quiet:
                print_info(f"Loaded {len(mcp_tools)} MCP tools from: {', '.join(mcp)}")

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

    def send_message(user_prompt: str) -> tuple[str | None, MessageStats]:
        """Send a message and return the response with stats."""
        nonlocal messages
        stats = MessageStats()

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
            return None, stats

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

                # Try to get generation stats (works for streaming mode)
                if generation_id:
                    try:
                        gen_stats = client.get_generation_stats(generation_id)
                        stats.prompt_tokens = gen_stats.tokens_prompt
                        stats.completion_tokens = gen_stats.tokens_completion
                        stats.total_tokens = gen_stats.tokens_prompt + gen_stats.tokens_completion
                        stats.cost = gen_stats.total_cost
                        
                        if show_cost:
                            printer.print_metadata(
                                model=model_used,
                                cost=stats.cost,
                                tokens={
                                    "prompt": stats.prompt_tokens,
                                    "completion": stats.completion_tokens,
                                    "total": stats.total_tokens,
                                },
                            )
                    except Exception:
                        # Stats unavailable - keep defaults of 0
                        pass

                # Add assistant response to messages
                messages.append({"role": "assistant", "content": full_response})
                return full_response, stats

            else:
                # Non-streaming with tool call loop
                while True:
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

                    choice = response.choices[0]
                    message = choice.message

                    # Check for tool calls
                    if message.tool_calls and mcp_manager:
                        # Accumulate stats from this intermediate response
                        if response.usage:
                            stats.prompt_tokens += response.usage.prompt_tokens or 0
                            stats.completion_tokens += response.usage.completion_tokens or 0
                            stats.total_tokens += response.usage.total_tokens or 0
                        
                        # Try to get cost from generation stats
                        if response.id:
                            try:
                                gen_stats = client.get_generation_stats(response.id)
                                stats.cost += gen_stats.total_cost
                            except Exception:
                                pass

                        # Add assistant message with tool calls
                        assistant_msg = {"role": "assistant", "content": message.content or ""}
                        assistant_msg["tool_calls"] = message.tool_calls
                        messages.append(assistant_msg)

                        # Execute each tool call
                        for tool_call in message.tool_calls:
                            # Parse the tool call with error handling
                            parsed = parse_tool_call(tool_call)
                            tc_id = parsed["id"]
                            func_name = parsed["name"]
                            args = parsed["arguments"]
                            
                            # Check for parsing errors
                            if parsed["error"]:
                                if not quiet:
                                    console.print(f"[yellow]Warning: {parsed['error']}[/yellow]")
                                # If we couldn't parse the function name, we can't proceed
                                if not func_name:
                                    result = format_tool_error(
                                        "json_parse", 
                                        func_name or "(unknown)", 
                                        parsed["error"]
                                    )
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "content": result,
                                    })
                                    continue

                            if verbose:
                                console.print(f"[dim]Tool call: {func_name}[/dim]")
                                console.print(f"[dim]Arguments: {json.dumps(args, indent=2)}[/dim]")
                            elif not quiet:
                                console.print(f"[dim]Calling tool: {func_name}[/dim]")

                            # Execute the tool call
                            exec_result = execute_tool_call(func_name, args, mcp_manager)
                            
                            if exec_result["success"]:
                                result = exec_result["result"]
                                if verbose:
                                    # Truncate long results for display
                                    display_result = result[:500] + "..." if len(result) > 500 else result
                                    console.print(f"[dim]Result: {display_result}[/dim]")
                            else:
                                result = f"Error: {exec_result['error']}"
                                if not quiet:
                                    console.print(f"[red]{result}[/red]")

                            # Add tool result
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "content": result,
                            })

                        # Continue loop to get next response
                        continue

                    # No tool calls - we have the final response
                    if output_json:
                        console.print_json(data=response.model_dump())
                    else:
                        content = message.content
                        if isinstance(content, str):
                            console.print(content)

                    # Capture usage stats from this response
                    if response.usage:
                        stats.prompt_tokens += response.usage.prompt_tokens or 0
                        stats.completion_tokens += response.usage.completion_tokens or 0
                        stats.total_tokens += response.usage.total_tokens or 0

                    # Try to get cost from generation stats
                    if response.id:
                        try:
                            gen_stats = client.get_generation_stats(response.id)
                            stats.cost += gen_stats.total_cost
                        except Exception:
                            # Cost unavailable - keep accumulated value
                            pass

                    if show_cost and (stats.total_tokens > 0 or stats.cost > 0):
                        printer.print_metadata(
                            model=response.model,
                            cost=stats.cost if stats.cost > 0 else None,
                            tokens={
                                "prompt": stats.prompt_tokens,
                                "completion": stats.completion_tokens,
                                "total": stats.total_tokens,
                            },
                        )

                    # Add assistant response to messages
                    assistant_content = message.content
                    messages.append({"role": "assistant", "content": assistant_content})

                    if isinstance(assistant_content, str):
                        return assistant_content, stats
                    return str(assistant_content) if assistant_content else "", stats

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

    # Track cumulative stats for the session
    session_tokens = 0
    session_cost = 0.0

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
                    _, msg_stats = send_message(user_input)
                    session_tokens += msg_stats.total_tokens
                    session_cost += msg_stats.cost
                    console.print()

                except EOFError:
                    break
                except KeyboardInterrupt:
                    console.print("\n[dim]Interrupted[/dim]")
                    break

        elif prompt:
            _, msg_stats = send_message(prompt)
            session_tokens += msg_stats.total_tokens
            session_cost += msg_stats.cost

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
            
            # Update conversation totals with session stats
            conv.total_tokens += session_tokens
            conv.total_cost += session_cost
            
            save_conversation(conv)
            if not quiet:
                print_info(f"Conversation saved as '{conversation}'")
                if session_tokens > 0 or session_cost > 0:
                    cost_str = f", ${session_cost:.6f}" if session_cost > 0 else ""
                    print_info(f"Session: {session_tokens} tokens{cost_str} | Total: {conv.total_tokens} tokens, ${conv.total_cost:.6f}")

    finally:
        client.close()


@click.command("chat")
@click.pass_context
def chat_command(ctx: click.Context) -> None:
    """Send a chat completion request."""
    ctx.invoke(chat)
