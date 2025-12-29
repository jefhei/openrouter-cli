"""Streaming output utilities."""

import sys
from typing import TextIO

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text


class StreamPrinter:
    """Handles streaming output of chat completions."""

    def __init__(
        self,
        output: TextIO | None = None,
        use_markdown: bool = True,
        quiet: bool = False,
    ):
        """Initialize the stream printer.

        Args:
            output: Output stream (defaults to stdout)
            use_markdown: Whether to render markdown
            quiet: Whether to suppress metadata output
        """
        self.output = output or sys.stdout
        self.use_markdown = use_markdown
        self.quiet = quiet
        self.console = Console(file=self.output)
        self._buffer = ""
        self._live: Live | None = None

    def start(self) -> None:
        """Start streaming output."""
        self._buffer = ""
        if self.use_markdown:
            self._live = Live(
                Text(""),
                console=self.console,
                refresh_per_second=10,
                transient=False,
            )
            self._live.start()

    def write(self, content: str) -> None:
        """Write content to the stream."""
        self._buffer += content

        if self._live and self.use_markdown:
            try:
                # Try to render as markdown
                self._live.update(Markdown(self._buffer))
            except Exception:
                # Fall back to plain text
                self._live.update(Text(self._buffer))
        else:
            # Plain text output
            self.output.write(content)
            self.output.flush()

    def finish(self) -> str:
        """Finish streaming and return the complete content."""
        if self._live:
            self._live.stop()
            self._live = None

        if not self.use_markdown and self._buffer:
            self.output.write("\n")
            self.output.flush()

        return self._buffer

    def print_metadata(self, **kwargs) -> None:
        """Print metadata (model, tokens, cost, etc.)."""
        if self.quiet:
            return

        self.console.print()

        if "model" in kwargs:
            self.console.print(f"[dim]Model: {kwargs['model']}[/dim]")

        if "tokens" in kwargs:
            tokens = kwargs["tokens"]
            self.console.print(
                f"[dim]Tokens: {tokens.get('prompt', 0)} prompt + "
                f"{tokens.get('completion', 0)} completion = "
                f"{tokens.get('total', 0)} total[/dim]"
            )

        if "cost" in kwargs:
            self.console.print(f"[dim]Cost: ${kwargs['cost']:.6f}[/dim]")

        if "generation_id" in kwargs:
            self.console.print(f"[dim]Generation ID: {kwargs['generation_id']}[/dim]")


class PlainStreamPrinter:
    """Simple plain-text stream printer for piping."""

    def __init__(self, output: TextIO | None = None):
        self.output = output or sys.stdout
        self._buffer = ""

    def start(self) -> None:
        self._buffer = ""

    def write(self, content: str) -> None:
        self._buffer += content
        self.output.write(content)
        self.output.flush()

    def finish(self) -> str:
        if self._buffer and not self._buffer.endswith("\n"):
            self.output.write("\n")
        return self._buffer

    def print_metadata(self, **kwargs) -> None:
        pass  # No metadata in plain mode


def create_printer(
    output: TextIO | None = None,
    use_markdown: bool = True,
    quiet: bool = False,
    plain: bool = False,
) -> StreamPrinter | PlainStreamPrinter:
    """Create an appropriate stream printer.

    Args:
        output: Output stream
        use_markdown: Whether to render markdown
        quiet: Whether to suppress metadata
        plain: Whether to use plain text only

    Returns:
        Appropriate stream printer instance
    """
    # Check if output is a TTY
    out = output or sys.stdout
    is_tty = hasattr(out, "isatty") and out.isatty()

    if plain or not is_tty:
        return PlainStreamPrinter(output)
    else:
        return StreamPrinter(output, use_markdown, quiet)
