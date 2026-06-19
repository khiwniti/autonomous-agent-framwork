"""Main CLI interface for the autonomous development agent."""

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from agent import __version__
from agent.config.settings import get_settings
from agent.core.engine import ReActEngine
from agent.llm.openai_client import OpenAIClient
from agent.memory.working import WorkingMemory
from agent.tools.base import get_tool_registry

console = Console()


def setup_logging(level: str = "INFO") -> None:
    """Set up logging with Rich handler.

    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.version_option(version=__version__)
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Autonomous Development Agent CLI.

    A production-grade AI-powered autonomous software development agent.
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    # Setup logging
    setup_logging("DEBUG" if debug else "INFO")


@cli.command()
@click.option(
    "--task",
    "-t",
    help="Task description to execute",
    prompt="Enter task",
)
@click.option(
    "--max-iterations",
    "-i",
    type=int,
    help="Maximum reasoning iterations",
)
@click.pass_context
def run(ctx: click.Context, task: str, max_iterations: int | None) -> None:
    """Execute a single task using the agent.

    Example:
        agent run --task "Create a Python function to calculate factorial"
    """
    asyncio.run(_run_task(task, max_iterations))


async def _run_task(task: str, max_iterations: int | None) -> None:
    """Execute task with agent.

    Args:
        task: Task description
        max_iterations: Max iterations override
    """
    settings = get_settings()

    # Display configuration
    console.print(
        Panel.fit(
            f"[bold cyan]Autonomous Development Agent[/bold cyan]\n"
            f"Version: {__version__}\n"
            f"LLM: {settings.llm_provider} ({settings.llm_model})\n"
            f"Max Iterations: {max_iterations or settings.agent_max_iterations}",
            title="Configuration",
        )
    )

    # Initialize components
    console.print("\n[yellow]Initializing agent...[/yellow]")

    async with OpenAIClient() as llm_client:
        async with WorkingMemory() as memory:
            tool_registry = get_tool_registry()

            # Register basic tools (Phase 1 - minimal set)
            from agent.tools.calculator import register_calculator_tool

            register_calculator_tool()
            # TODO: Add more tools in Phase 2
            console.print(
                f"[green]✓[/green] Registered {len(tool_registry.list_tools())} tools"
            )

            engine = ReActEngine(
                llm_client=llm_client,
                tool_registry=tool_registry,
                max_iterations=max_iterations,
            )

            # Execute task
            console.print(f"\n[bold]Task:[/bold] {task}\n")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task_progress = progress.add_task(
                    "[cyan]Executing...", total=None
                )

                try:
                    result = await engine.execute(task)
                    progress.update(task_progress, completed=True)

                    # Display results
                    _display_result(result)

                except Exception as e:
                    progress.update(task_progress, completed=True)
                    console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
                    raise

            await engine.close()


def _display_result(result) -> None:
    """Display execution result.

    Args:
        result: ExecutionResult to display
    """
    # Status
    status_color = "green" if result.success else "red"
    status_text = "✓ Success" if result.success else "✗ Failed"

    console.print(f"\n[bold {status_color}]{status_text}[/bold {status_color}]")

    # Output
    if result.output:
        console.print(
            Panel(
                result.output,
                title="Output",
                border_style="green" if result.success else "red",
            )
        )

    # Error
    if result.error:
        console.print(Panel(result.error, title="Error", border_style="red"))

    # Execution steps
    if result.steps:
        table = Table(title=f"Execution Steps ({result.iterations} iterations)")
        table.add_column("Step", style="cyan", no_wrap=True)
        table.add_column("Action", style="magenta")
        table.add_column("Observation", style="green")

        for step in result.steps[-10:]:  # Show last 10 steps
            table.add_row(
                str(step.iteration),
                step.action or "-",
                (step.observation or step.thought or "-")[:100] + "...",
            )

        console.print("\n")
        console.print(table)

    # Metadata
    console.print(f"\n[dim]Iterations: {result.iterations}[/dim]")


@cli.command()
def interactive() -> None:
    """Start interactive agent session."""
    console.print(
        Panel.fit(
            "[bold cyan]Interactive Agent Session[/bold cyan]\n"
            "Type tasks and get instant results.\n"
            "Commands: 'exit', 'quit', 'help'",
            title="Welcome",
        )
    )

    asyncio.run(_interactive_session())


async def _interactive_session() -> None:
    """Run interactive session."""
    settings = get_settings()

    async with OpenAIClient() as llm_client:
        async with WorkingMemory() as memory:
            tool_registry = get_tool_registry()

            # Register tools
            from agent.tools.calculator import register_calculator_tool

            register_calculator_tool()

            engine = ReActEngine(
                llm_client=llm_client,
                tool_registry=tool_registry,
            )

            console.print(
                f"\n[green]✓[/green] Agent ready with {len(tool_registry.list_tools())} tools\n"
            )

            while True:
                try:
                    task = Prompt.ask("\n[bold cyan]Task[/bold cyan]")

                    if task.lower() in ["exit", "quit", "q"]:
                        console.print("[yellow]Goodbye![/yellow]")
                        break

                    if task.lower() == "help":
                        _display_help()
                        continue

                    if not task.strip():
                        continue

                    # Execute task
                    result = await engine.execute(task)
                    _display_result(result)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
                except Exception as e:
                    console.print(f"[bold red]Error:[/bold red] {str(e)}")

            await engine.close()


def _display_help() -> None:
    """Display help information."""
    help_text = """
[bold]Available Commands:[/bold]
- [cyan]exit/quit[/cyan]: Exit interactive mode
- [cyan]help[/cyan]: Show this help message

[bold]Tips:[/bold]
- Be specific in task descriptions
- Agent will reason step-by-step
- Check execution steps for debugging
"""
    console.print(Panel(help_text, title="Help"))


@cli.command()
def info() -> None:
    """Display agent configuration and status."""
    settings = get_settings()

    # Configuration table
    table = Table(title="Agent Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Version", __version__)
    table.add_row("Environment", settings.environment)
    table.add_row("Debug Mode", str(settings.debug))
    table.add_row("", "")
    table.add_row("LLM Provider", settings.llm_provider)
    table.add_row("LLM Model", settings.llm_model)
    table.add_row("API Base URL", settings.llm_api_base_url)
    table.add_row("", "")
    table.add_row("Max Iterations", str(settings.agent_max_iterations))
    table.add_row("Reflection Interval", str(settings.agent_reflection_interval))
    table.add_row("", "")
    table.add_row("Memory Backend", settings.memory_backend)
    table.add_row("Memory TTL", f"{settings.memory_ttl}s")
    table.add_row("", "")
    table.add_row("Sandbox Enabled", str(settings.sandbox_enabled))
    table.add_row("Sandbox Network", settings.sandbox_network_mode)

    console.print("\n")
    console.print(table)
    console.print("\n")


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
def validate_config(config_file: str) -> None:
    """Validate configuration file.

    Args:
        config_file: Path to .env file
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(config_file)
        settings = get_settings()

        console.print("[green]✓[/green] Configuration is valid")
        console.print(f"\nLLM Provider: {settings.llm_provider}")
        console.print(f"Model: {settings.llm_model}")

    except Exception as e:
        console.print(f"[red]✗[/red] Configuration error: {str(e)}")
        raise click.Abort()


if __name__ == "__main__":
    cli()
