"""CLI entry point using click."""

import asyncio

import click

from myaicoder import __version__


@click.group(invoke_without_command=True)
@click.option("--model", default=None, help="Model name (default: from config)")
@click.option("--vllm-url", default=None, help="vLLM server URL (default: http://localhost:8080/v1)")
@click.option("--no-stream", is_flag=True, help="Disable streaming output")
@click.option("--no-tools", is_flag=True, help="Disable all tools")
@click.option("--verbose", is_flag=True, help="Show debug information")
@click.option("-p", "--prompt", default=None, help="One-shot prompt (non-interactive)")
@click.version_option(version=__version__)
@click.pass_context
def main(ctx, model, vllm_url, no_stream, no_tools, verbose, prompt):
    """myAiCoder - AI Coding Assistant powered by local LLM."""
    if ctx.invoked_subcommand is not None:
        return

    ctx.ensure_object(dict)
    ctx.obj["model"] = model
    ctx.obj["vllm_url"] = vllm_url
    ctx.obj["no_stream"] = no_stream
    ctx.obj["no_tools"] = no_tools
    ctx.obj["verbose"] = verbose

    asyncio.run(_run_chat(model, vllm_url, no_stream, no_tools, verbose, prompt))


async def _run_chat(
    model: str | None,
    vllm_url: str | None,
    no_stream: bool,
    no_tools: bool,
    verbose: bool,
    prompt: str | None,
):
    """Run interactive or one-shot chat."""
    from myaicoder.core.config import AppConfig
    from myaicoder.core.context import ContextManager
    from myaicoder.core.engine import AgentEngine
    from myaicoder.llm.vllm_provider import VLLMProvider
    from myaicoder.tools.registry import create_default_registry
    from myaicoder.ui.chat import ChatUI

    config = AppConfig.load()

    # CLI overrides
    if model:
        config.llm.model = model
    if vllm_url:
        config.llm.base_url = vllm_url
    if no_tools:
        config.tools.enabled = False

    llm = VLLMProvider(
        base_url=config.llm.base_url,
        model=config.llm.model,
        max_tokens=config.llm.max_tokens,
    )
    context = ContextManager()
    ui = ChatUI(
        show_token_usage=config.ui.show_token_usage,
        markdown_render=config.ui.markdown_render,
    )

    # Setup tools (unless disabled)
    tool_registry = None
    mcp_client = None

    if config.tools.enabled:
        tool_registry = create_default_registry()

        # Connect MCP servers if configured
        try:
            from myaicoder.mcp.client import MCPClient
            from myaicoder.mcp.config import MCPConfig

            mcp_config = MCPConfig.load()
            if mcp_config.servers:
                mcp_client = MCPClient(config=mcp_config)
                connected = await mcp_client.connect_all()
                if connected:
                    mcp_tools = await mcp_client.discover_tools()
                    for tool in mcp_tools:
                        tool_registry.register(tool)
                    if verbose:
                        for server, tools in connected.items():
                            ui.print_info(f"MCP '{server}': {len(tools)} tools")
        except Exception as e:
            if verbose:
                ui.print_info(f"MCP: {e}")

    engine = AgentEngine(
        llm=llm,
        context_manager=context,
        tool_registry=tool_registry,
        approval_callback=ui.prompt_tool_approval if tool_registry else None,
        require_approval=config.tools.require_approval if tool_registry else None,
    )
    # Health check
    if verbose:
        ui.print_info(f"Connecting to vLLM at {config.llm.base_url}...")

    healthy = await llm.health_check()
    if not healthy:
        ui.print_error(
            f"Cannot connect to vLLM server at {config.llm.base_url}\n"
            "  Start vLLM with: vllm serve <model> --host 0.0.0.0 --port 8080\n"
            "  Or specify URL:  myaicoder --vllm-url http://host:port/v1"
        )
        return

    if verbose:
        ui.print_info(f"Connected. Model: {config.llm.model}")

    # One-shot mode
    if prompt:
        await _one_shot(engine, ui, prompt, no_stream)
        if mcp_client:
            await mcp_client.close()
        return

    # Interactive mode
    ui.print_welcome()

    while True:
        try:
            user_input = ui.get_input()
        except KeyboardInterrupt:
            ui.print_goodbye()
            break

        if user_input is None:
            ui.print_goodbye()
            break

        if not user_input:
            continue

        # Built-in commands
        if user_input.startswith("/"):
            if _handle_command(user_input, engine, ui):
                continue
            if user_input == "/quit":
                ui.print_goodbye()
                break

        try:
            if no_stream:
                response = await engine.chat(user_input)
                ui.print_assistant(response)
            else:
                ui.print_streaming_start()
                async for chunk in engine.chat_stream(user_input):
                    ui.print_streaming_chunk(chunk)
                ui.print_streaming_end()
        except Exception as e:
            ui.print_error(str(e))

    if mcp_client:
        await mcp_client.close()


async def _one_shot(engine, ui, prompt: str, no_stream: bool):
    """Single prompt → response, then exit."""
    try:
        if no_stream:
            response = await engine.chat(prompt)
            ui.print_assistant(response)
        else:
            ui.print_streaming_start()
            async for chunk in engine.chat_stream(prompt):
                ui.print_streaming_chunk(chunk)
            ui.print_streaming_end()
    except Exception as e:
        ui.print_error(str(e))


def _handle_command(command: str, engine, ui) -> bool:
    """Handle slash commands. Returns True if handled."""
    cmd = command.lower().strip()

    if cmd == "/help":
        ui.console.print(
            "\n[bold]Commands:[/bold]\n"
            "  /help     Show this help\n"
            "  /clear    Clear conversation history\n"
            "  /quit     Exit myAiCoder\n"
        )
        return True

    if cmd == "/clear":
        engine.reset()
        ui.print_info("Conversation cleared.")
        return True

    if cmd == "/quit":
        return False  # Let the caller handle exit

    ui.print_info(f"Unknown command: {command}")
    return True


@main.command()
def config():
    """Show current configuration."""
    from myaicoder.core.config import AppConfig

    cfg = AppConfig.load()
    click.echo(f"LLM Provider: {cfg.llm.provider}")
    click.echo(f"LLM Base URL: {cfg.llm.base_url}")
    click.echo(f"LLM Model:    {cfg.llm.model}")
    click.echo(f"Max Tokens:   {cfg.llm.max_tokens}")


@main.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "streamable-http"]),
    help="MCP transport (default: stdio)",
)
@click.option("--port", default=3000, help="HTTP port (default: 3000)")
@click.option(
    "--allow-bash",
    is_flag=True,
    help="Allow Bash tool (disabled by default for safety)",
)
@click.option(
    "--working-dir",
    default=None,
    help="Restrict file operations to this directory",
)
@click.option(
    "--max-concurrent",
    default=1,
    help="Max concurrent requests (default: 1)",
)
@click.option(
    "--agentic",
    is_flag=True,
    help="Enable agentic_task tool for multi-step execution",
)
def serve(transport, port, allow_bash, working_dir, max_concurrent, agentic):
    """Run as MCP server (for Claude Code, Cursor, etc.)."""
    from myaicoder.mcp.server import MCPServer
    from myaicoder.tools.registry import create_default_registry

    registry = create_default_registry()

    llm_provider = None
    if agentic:
        from myaicoder.core.config import AppConfig
        from myaicoder.llm.vllm_provider import VLLMProvider

        config = AppConfig.load()
        llm_provider = VLLMProvider(
            base_url=config.llm.base_url,
            model=config.llm.model,
            max_tokens=config.llm.max_tokens,
        )

    server = MCPServer(
        tool_registry=registry,
        allow_bash=allow_bash,
        working_dir=working_dir,
        max_concurrent=max_concurrent,
        enable_agentic=agentic,
        llm_provider=llm_provider,
    )

    if transport == "streamable-http":
        import os

        os.environ.setdefault("FASTMCP_PORT", str(port))

    server.run(transport=transport)


@main.group()
def mcp():
    """MCP server management."""
    pass


@mcp.command("list")
def mcp_list():
    """List configured MCP servers."""
    from myaicoder.mcp.config import MCPConfig

    cfg = MCPConfig.load()
    if not cfg.servers:
        click.echo("No MCP servers configured.")
        click.echo("Create .mcp.json in your project root to add servers.")
        return

    click.echo(f"MCP Servers ({len(cfg.servers)}):\n")
    for name, server in cfg.servers.items():
        click.echo(f"  {name}")
        click.echo(f"    Transport: {server.transport}")
        if server.command:
            cmd = f"{server.command} {' '.join(server.args)}"
            click.echo(f"    Command:   {cmd}")
        if server.url:
            click.echo(f"    URL:       {server.url}")
        click.echo()


def _build_model_manager():
    """Build ModelManager with config-driven backend."""
    from myaicoder.models.config import ModelsConfig
    from myaicoder.models.manager import ModelManager
    from myaicoder.models.process import VLLMProcessManager
    from myaicoder.models.scanner import ModelScanner

    config = ModelsConfig.load()
    pm = VLLMProcessManager(
        backend=config.backend,
        command=config.backend_command,
    )
    scanner = ModelScanner(config.models_dir, config)
    return ModelManager(config, pm, scanner), config


@main.group()
def model():
    """Model management commands."""
    pass


@model.command("list")
def model_list():
    """List available models and their status."""
    from myaicoder.models.manager import ModelStatus

    mgr, config = _build_model_manager()

    models = mgr.list_models()
    env_info = "DGX Spark, 128GB" if config.is_prod() else "Desktop"
    click.echo(f"  ENV: {config.environment} ({env_info})\n")

    if config.is_prod():
        click.echo(f"  {'NAME':<20} {'SIZE':<8} {'PORT':<6} {'STATUS':<12} DESCRIPTION")
        for m in models:
            status_str = "loaded ●" if m.status == ModelStatus.LOADED else m.status.value
            port_str = str(m.port) if m.port else "-"
            click.echo(
                f"  {m.name:<20} {m.size_human:<8} {port_str:<6} {status_str:<12} {m.description}"
            )
    else:
        click.echo(f"  {'NAME':<20} {'SIZE':<8} {'STATUS':<12} DESCRIPTION")
        for m in models:
            status_str = "loaded ●" if m.status == ModelStatus.LOADED else m.status.value
            click.echo(
                f"  {m.name:<20} {m.size_human:<8} {status_str:<12} {m.description}"
            )


@model.command("switch")
@click.argument("name")
def model_switch(name):
    """Switch to a different model (dev environment only)."""
    mgr, config = _build_model_manager()

    def on_status(msg: str) -> None:
        click.echo(f"  ⏳ {msg}")

    try:
        result = asyncio.run(mgr.switch_model(name, on_status=on_status))
        click.echo(f"  ✓ Model switched to {result.name}")
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        click.echo(f"  ✗ {e}", err=True)
        raise SystemExit(1)


@model.command("status")
def model_status():
    """Show current model and environment status."""
    mgr, config = _build_model_manager()

    status = mgr.get_status()
    click.echo(f"  Environment: {status['environment']}")
    click.echo(f"  Models dir:  {status['models_dir']}")
    click.echo(f"  Loaded:      {status['loaded_models']}/{status['total_models']}")
    for m in status["models"]:
        click.echo(f"    {m['name']} (:{m['port']}) — {m['state']}")


@model.command("launch")
@click.option(
    "--env",
    type=click.Choice(["prod", "dev"]),
    default=None,
    help="Environment override",
)
def model_launch(env):
    """Launch LLM server for the current environment."""
    mgr, config = _build_model_manager()
    if env:
        config.environment = env

    def on_status(msg: str) -> None:
        click.echo(f"  ⏳ {msg}")

    try:
        instances = asyncio.run(mgr.launch(on_status=on_status))
        click.echo(f"\n  ✓ {len(instances)} model(s) launched")
    except (RuntimeError, FileNotFoundError) as e:
        click.echo(f"  ✗ Launch failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
