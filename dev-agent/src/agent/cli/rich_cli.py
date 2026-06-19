"""Enhanced CLI with rich formatting - Phase 5."""

import asyncio
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from rich.live import Live
from rich.layout import Layout
from rich import box

from agent.agents.base import AgentRole, AgentTask, TaskStatus
from agent.api.rest import AgentAPI
from agent.core.orchestrator import AgentOrchestrator, WorkflowStage, WorkflowStatus
from agent.session.manager import Session, SessionManager


class RichCLI:
    """Enhanced CLI with rich formatting."""

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        session_manager: SessionManager | None = None,
    ):
        """Initialize rich CLI.

        Args:
            orchestrator: Agent orchestrator
            session_manager: Optional session manager

        """
        self.console = Console()
        self.orchestrator = orchestrator
        self.session_manager = session_manager or SessionManager()
        self.current_session: Session | None = None

    def print_header(self, title: str) -> None:
        """Print formatted header.

        Args:
            title: Header title

        """
        self.console.print(
            Panel(
                f"[bold cyan]{title}[/bold cyan]",
                box=box.DOUBLE,
                border_style="cyan",
            )
        )

    def print_success(self, message: str) -> None:
        """Print success message.

        Args:
            message: Success message

        """
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def print_error(self, message: str) -> None:
        """Print error message.

        Args:
            message: Error message

        """
        self.console.print(f"[bold red]✗[/bold red] {message}")

    def print_warning(self, message: str) -> None:
        """Print warning message.

        Args:
            message: Warning message

        """
        self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")

    def print_info(self, message: str) -> None:
        """Print info message.

        Args:
            message: Info message

        """
        self.console.print(f"[bold blue]ℹ[/bold blue] {message}")

    def print_code(self, code: str, language: str = "python") -> None:
        """Print syntax-highlighted code.

        Args:
            code: Code to display
            language: Programming language

        """
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def create_task_table(self, tasks: list[AgentTask]) -> Table:
        """Create table of tasks.

        Args:
            tasks: List of tasks

        Returns:
            Rich table

        """
        table = Table(title="Tasks", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Role", style="magenta")
        table.add_column("Objective", style="white")
        table.add_column("Status", style="green")

        for task in tasks:
            status_color = {
                TaskStatus.PENDING: "yellow",
                TaskStatus.IN_PROGRESS: "blue",
                TaskStatus.COMPLETED: "green",
                TaskStatus.FAILED: "red",
            }.get(task.status, "white")

            table.add_row(
                task.id,
                task.role.value,
                task.objective[:50] + "..." if len(task.objective) > 50 else task.objective,
                f"[{status_color}]{task.status.value}[/{status_color}]",
            )

        return table

    def create_session_table(self, sessions: list[Session]) -> Table:
        """Create table of sessions.

        Args:
            sessions: List of sessions

        Returns:
            Rich table

        """
        table = Table(title="Sessions", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Created", style="white")
        table.add_column("Tasks", style="green")
        table.add_column("Messages", style="blue")
        table.add_column("Active", style="yellow")

        for session in sessions:
            table.add_row(
                session.id,
                session.name or "Unnamed",
                session.created_at.strftime("%Y-%m-%d %H:%M"),
                str(len(session.tasks)),
                str(len(session.messages)),
                "✓" if session.is_active else "✗",
            )

        return table

    def create_workflow_tree(self, workflow: Any) -> Tree:
        """Create tree visualization of workflow.

        Args:
            workflow: Workflow object

        Returns:
            Rich tree

        """
        tree = Tree(f"[bold cyan]Workflow:[/bold cyan] {workflow.name}")

        # Add workflow details
        status_color = {
            WorkflowStatus.PENDING: "yellow",
            WorkflowStatus.IN_PROGRESS: "blue",
            WorkflowStatus.COMPLETED: "green",
            WorkflowStatus.FAILED: "red",
        }.get(workflow.status, "white")

        tree.add(f"[bold]Status:[/bold] [{status_color}]{workflow.status.value}[/{status_color}]")
        tree.add(f"[bold]Objective:[/bold] {workflow.objective}")

        # Add stages
        stages_branch = tree.add("[bold]Stages:[/bold]")
        for stage in workflow.stages:
            stage_status = "✓" if workflow.current_stage and stage.value == workflow.current_stage.value else "○"
            stages_branch.add(f"{stage_status} {stage.value}")

        # Add tasks
        tasks_branch = tree.add(f"[bold]Tasks:[/bold] ({len(workflow.tasks)})")
        for task in workflow.tasks:
            task_status_color = {
                TaskStatus.PENDING: "yellow",
                TaskStatus.IN_PROGRESS: "blue",
                TaskStatus.COMPLETED: "green",
                TaskStatus.FAILED: "red",
            }.get(task.status, "white")

            tasks_branch.add(
                f"[{task_status_color}]{task.role.value}[/{task_status_color}]: {task.objective[:40]}..."
            )

        return tree

    async def execute_task_with_progress(self, task: AgentTask) -> AgentTask:
        """Execute task with progress display.

        Args:
            task: Task to execute

        Returns:
            Completed task

        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
            console=self.console,
        ) as progress:
            task_progress = progress.add_task(
                f"[cyan]Executing {task.role.value}...", total=100
            )

            # Get agent
            agent = self.orchestrator.agents.get(task.role)
            if not agent:
                self.print_error(f"No agent found for role {task.role}")
                task.status = TaskStatus.FAILED
                return task

            # Execute task with progress updates
            progress.update(task_progress, advance=20, description="[cyan]Initializing...")
            await asyncio.sleep(0.1)

            progress.update(task_progress, advance=30, description="[cyan]Processing...")
            result = await agent.process_task(task)

            progress.update(
                task_progress,
                advance=50,
                description=f"[green]Completed {task.role.value}",
            )

            return result

    async def execute_workflow_with_progress(self, workflow_id: str) -> Any:
        """Execute workflow with progress display.

        Args:
            workflow_id: Workflow ID

        Returns:
            Completed workflow

        """
        workflow = self.orchestrator.workflows.get(workflow_id)
        if not workflow:
            self.print_error(f"Workflow not found: {workflow_id}")
            return None

        self.print_header(f"Executing Workflow: {workflow.name}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        ) as progress:
            workflow_progress = progress.add_task(
                "[cyan]Workflow progress...", total=len(workflow.stages)
            )

            for i, stage in enumerate(workflow.stages):
                progress.update(
                    workflow_progress,
                    advance=i,
                    description=f"[cyan]Stage: {stage.value}",
                )

                # Create stage task
                task = await self.orchestrator._create_stage_task(workflow, stage)

                # Execute stage task
                progress.update(
                    workflow_progress,
                    description=f"[blue]Executing: {stage.value}",
                )
                result_task = await self.orchestrator._execute_stage_task(task)

                if result_task.status == TaskStatus.COMPLETED:
                    progress.update(
                        workflow_progress,
                        advance=1,
                        description=f"[green]Completed: {stage.value}",
                    )
                else:
                    progress.update(
                        workflow_progress,
                        description=f"[red]Failed: {stage.value}",
                    )
                    break

            progress.update(
                workflow_progress,
                completed=len(workflow.stages),
                description="[green]Workflow completed",
            )

        return workflow

    async def interactive_session(self) -> None:
        """Run interactive session."""
        self.print_header("Autonomous Agent CLI")
        self.console.print("[bold]Welcome to the Autonomous Agent System[/bold]\n")

        while True:
            # Main menu
            self.console.print("\n[bold cyan]Main Menu:[/bold cyan]")
            self.console.print("1. Create new session")
            self.console.print("2. List sessions")
            self.console.print("3. Execute agent task")
            self.console.print("4. Execute workflow")
            self.console.print("5. View session details")
            self.console.print("6. Exit")

            choice = Prompt.ask(
                "[bold]Select option[/bold]", choices=["1", "2", "3", "4", "5", "6"]
            )

            try:
                if choice == "1":
                    await self._create_session_interactive()
                elif choice == "2":
                    await self._list_sessions_interactive()
                elif choice == "3":
                    await self._execute_task_interactive()
                elif choice == "4":
                    await self._execute_workflow_interactive()
                elif choice == "5":
                    await self._view_session_interactive()
                elif choice == "6":
                    if Confirm.ask("[bold]Exit?[/bold]"):
                        self.print_success("Goodbye!")
                        break

            except KeyboardInterrupt:
                self.print_warning("\nOperation cancelled")
            except Exception as e:
                self.print_error(f"Error: {str(e)}")

    async def _create_session_interactive(self) -> None:
        """Create session interactively."""
        name = Prompt.ask("[bold]Session name[/bold]", default="Unnamed")
        session = await self.session_manager.create_session(name=name)
        self.current_session = session
        self.print_success(f"Created session: {session.id}")

    async def _list_sessions_interactive(self) -> None:
        """List sessions interactively."""
        sessions = await self.session_manager.list_sessions()
        if not sessions:
            self.print_info("No sessions found")
            return

        table = self.create_session_table(sessions)
        self.console.print(table)

    async def _execute_task_interactive(self) -> None:
        """Execute task interactively."""
        if not self.current_session:
            self.print_warning("No active session. Create one first.")
            return

        # Select agent role
        self.console.print("\n[bold]Select agent role:[/bold]")
        roles = list(AgentRole)
        for i, role in enumerate(roles, 1):
            self.console.print(f"{i}. {role.value}")

        role_idx = int(Prompt.ask("[bold]Role[/bold]", choices=[str(i) for i in range(1, len(roles) + 1)])) - 1
        role = roles[role_idx]

        # Get objective
        objective = Prompt.ask("[bold]Task objective[/bold]")

        # Create and execute task
        task = AgentTask(
            id=f"task_{datetime.now().timestamp()}",
            role=role,
            objective=objective,
        )

        result = await self.execute_task_with_progress(task)

        # Display result
        if result.status == TaskStatus.COMPLETED:
            self.print_success(f"Task completed: {result.id}")
            if result.result:
                self.console.print(Panel(str(result.result), title="Result"))
        else:
            self.print_error(f"Task failed: {result.error or 'Unknown error'}")

        # Add to session
        await self.current_session.add_task(result)

    async def _execute_workflow_interactive(self) -> None:
        """Execute workflow interactively."""
        name = Prompt.ask("[bold]Workflow name[/bold]")
        objective = Prompt.ask("[bold]Workflow objective[/bold]")

        # Select stages
        self.console.print("\n[bold]Select stages (comma-separated):[/bold]")
        stages = list(WorkflowStage)
        for i, stage in enumerate(stages, 1):
            self.console.print(f"{i}. {stage.value}")

        stage_input = Prompt.ask("[bold]Stages[/bold]", default="1,2,3,4,5,6")
        stage_indices = [int(idx.strip()) - 1 for idx in stage_input.split(",")]
        selected_stages = [stages[i] for i in stage_indices]

        # Create workflow
        workflow = await self.orchestrator.create_workflow(
            name=name,
            objective=objective,
            stages=selected_stages,
        )

        # Execute workflow
        result = await self.execute_workflow_with_progress(workflow.id)

        # Display result
        if result.status == WorkflowStatus.COMPLETED:
            self.print_success("Workflow completed!")
            tree = self.create_workflow_tree(result)
            self.console.print(tree)
        else:
            self.print_error(f"Workflow failed: {result.error or 'Unknown error'}")

    async def _view_session_interactive(self) -> None:
        """View session details interactively."""
        if not self.current_session:
            self.print_warning("No active session")
            return

        # Display session info
        self.print_header(f"Session: {self.current_session.name or self.current_session.id}")

        self.console.print(f"\n[bold]Created:[/bold] {self.current_session.created_at}")
        self.console.print(f"[bold]Last Activity:[/bold] {self.current_session.last_activity}")

        # Display tasks
        if self.current_session.tasks:
            table = self.create_task_table(self.current_session.tasks)
            self.console.print("\n", table)

            # Display task summary
            summary = await self.current_session.get_task_summary()
            self.console.print(f"\n[bold]Task Summary:[/bold]")
            self.console.print(f"  Total: {summary['total']}")
            self.console.print(f"  Completed: {summary['completed']}")
            self.console.print(f"  Success Rate: {summary['success_rate']:.1%}")
        else:
            self.print_info("No tasks in session")


async def main():
    """Run interactive CLI."""
    from agent.llm.mock import MockLLMClient
    from agent.memory.working import WorkingMemory
    from agent.tools.base import ToolRegistry
    from agent.core.orchestrator import create_orchestrator

    # Initialize components
    llm_client = MockLLMClient()
    tool_registry = ToolRegistry()
    memory = WorkingMemory()
    orchestrator = await create_orchestrator(llm_client, tool_registry, memory)
    session_manager = SessionManager()

    # Run interactive CLI
    cli = RichCLI(orchestrator, session_manager)
    await cli.interactive_session()


if __name__ == "__main__":
    asyncio.run(main())
