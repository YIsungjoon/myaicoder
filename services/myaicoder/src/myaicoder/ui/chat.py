"""Terminal chat UI using rich."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel


class ChatUI:
    """Rich-based terminal UI for interactive chat."""

    def __init__(self, show_token_usage: bool = True, markdown_render: bool = True):
        self.console = Console()
        self.show_token_usage = show_token_usage
        self.markdown_render = markdown_render

    def print_welcome(self) -> None:
        self.console.print()
        self.console.print(
            Panel(
                "[bold cyan]myAiCoder[/bold cyan] - AI Coding Assistant\n"
                "[dim]Powered by local LLM | Type /help for commands | Ctrl+C to exit[/dim]",
                border_style="cyan",
            )
        )
        self.console.print()

    def print_assistant(self, text: str) -> None:
        self.console.print()
        if self.markdown_render:
            self.console.print(Markdown(text))
        else:
            self.console.print(text)
        self.console.print()

    def print_streaming_start(self) -> None:
        self.console.print()

    def print_streaming_chunk(self, chunk: str) -> None:
        self.console.print(chunk, end="", highlight=False)

    def print_streaming_end(self) -> None:
        self.console.print()
        self.console.print()

    def print_error(self, message: str) -> None:
        self.console.print(f"\n[bold red]Error:[/bold red] {message}\n")

    def print_info(self, message: str) -> None:
        self.console.print(f"[dim]{message}[/dim]")

    def print_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        if self.show_token_usage:
            total = prompt_tokens + completion_tokens
            self.console.print(
                f"[dim]tokens: {prompt_tokens} in / {completion_tokens} out / {total} total[/dim]"
            )

    def print_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Display a tool call with its arguments."""
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        # Truncate long argument values
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        self.console.print(
            f"[bold yellow]Tool:[/bold yellow] {tool_name}({args_str})"
        )

    def prompt_tool_approval(self, tool_name: str, arguments: dict) -> bool:
        """Ask user to approve a tool execution. Returns True if approved."""
        self.print_tool_call(tool_name, arguments)
        try:
            response = self.console.input(
                "[bold yellow]Allow?[/bold yellow] [dim](y/n/a)[/dim] "
            ).strip().lower()
            return response in ("y", "yes", "a", "allow", "")
        except (EOFError, KeyboardInterrupt):
            return False

    def print_tool_result(self, tool_name: str, success: bool) -> None:
        """Display tool execution result status."""
        status = "[green]OK[/green]" if success else "[red]FAILED[/red]"
        self.console.print(f"[dim]  {tool_name}: {status}[/dim]")

    def get_input(self) -> str | None:
        """Get user input with prompt. Returns None on EOF/Ctrl+D."""
        try:
            text = self.console.input("[bold green]>[/bold green] ")
            return text.strip()
        except EOFError:
            return None

    def print_goodbye(self) -> None:
        self.console.print("\n[dim]Goodbye![/dim]")
