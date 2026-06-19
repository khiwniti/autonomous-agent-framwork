"""Agent orchestrator for coordinating SDLC workflows across specialized agents."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agent.agents.base import AgentRole, AgentTask, BaseAgent, TaskStatus
from agent.llm.base import BaseLLMClient
from agent.memory.working import WorkingMemory
from agent.tools.base import ToolRegistry


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class WorkflowStage(str, Enum):
    """SDLC workflow stages."""

    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    OPERATIONS = "operations"


class Workflow(BaseModel):
    """SDLC workflow definition."""

    id: str = Field(description="Unique workflow ID")
    name: str = Field(description="Workflow name")
    objective: str = Field(description="Overall workflow objective")
    stages: list[WorkflowStage] = Field(
        default_factory=list, description="Workflow stages to execute"
    )
    current_stage: WorkflowStage | None = Field(default=None, description="Current stage")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Workflow status")
    tasks: list[AgentTask] = Field(default_factory=list, description="All tasks in workflow")
    context: dict[str, Any] = Field(default_factory=dict, description="Shared workflow context")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )
    started_at: datetime | None = Field(default=None, description="Start timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    error: str | None = Field(default=None, description="Error message if failed")


class AgentOrchestrator:
    """Orchestrates SDLC workflows across specialized agents."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        tool_registry: ToolRegistry,
        memory: WorkingMemory | None = None,
    ):
        """Initialize agent orchestrator.

        Args:
            llm_client: LLM client for agents
            tool_registry: Tool registry for agents
            memory: Shared working memory

        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.memory = memory or WorkingMemory()
        self.agents: dict[AgentRole, BaseAgent] = {}
        self.workflows: dict[str, Workflow] = {}

    async def register_agent(self, role: AgentRole, agent: BaseAgent) -> None:
        """Register a specialized agent.

        Args:
            role: Agent role
            agent: Agent instance

        """
        self.agents[role] = agent

    async def create_workflow(
        self,
        name: str,
        objective: str,
        stages: list[WorkflowStage] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Workflow:
        """Create a new SDLC workflow.

        Args:
            name: Workflow name
            objective: Overall objective
            stages: Workflow stages (defaults to full SDLC)
            context: Initial workflow context

        Returns:
            Created workflow

        """
        workflow_id = f"workflow_{datetime.now(timezone.utc).timestamp()}"

        # Default to full SDLC pipeline if no stages specified
        if stages is None:
            stages = list(WorkflowStage)

        workflow = Workflow(
            id=workflow_id,
            name=name,
            objective=objective,
            stages=stages,
            context=context or {},
        )

        self.workflows[workflow_id] = workflow
        return workflow

    async def execute_workflow(self, workflow_id: str) -> Workflow:
        """Execute a workflow through all stages.

        Args:
            workflow_id: Workflow to execute

        Returns:
            Completed workflow with results

        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.started_at = datetime.now(timezone.utc)

        try:
            # Execute each stage in sequence
            for stage in workflow.stages:
                workflow.current_stage = stage

                # Create task for this stage
                task = await self._create_stage_task(workflow, stage)
                workflow.tasks.append(task)

                # Execute task with appropriate agent
                result_task = await self._execute_stage_task(task)

                # Update workflow context with stage results
                if result_task.result:
                    workflow.context[f"{stage}_result"] = result_task.result

                # Handle task failure
                if result_task.status == TaskStatus.FAILED:
                    workflow.status = WorkflowStatus.FAILED
                    workflow.error = result_task.error
                    workflow.completed_at = datetime.now(timezone.utc)
                    return workflow

            # Workflow completed successfully
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            workflow.completed_at = datetime.now(timezone.utc)

        return workflow

    async def _create_stage_task(self, workflow: Workflow, stage: WorkflowStage) -> AgentTask:
        """Create a task for a workflow stage.

        Args:
            workflow: Parent workflow
            stage: Workflow stage

        Returns:
            Created task

        """
        # Map stage to agent role
        role_mapping = {
            WorkflowStage.REQUIREMENTS: AgentRole.REQUIREMENTS,
            WorkflowStage.ARCHITECTURE: AgentRole.ARCHITECTURE,
            WorkflowStage.IMPLEMENTATION: AgentRole.IMPLEMENTATION,
            WorkflowStage.TESTING: AgentRole.TESTING,
            WorkflowStage.DEPLOYMENT: AgentRole.DEPLOYMENT,
            WorkflowStage.OPERATIONS: AgentRole.OPERATIONS,
        }

        role = role_mapping[stage]

        # Build task objective based on stage and previous results
        objective = self._build_stage_objective(workflow, stage)

        # Collect dependencies from previous stages
        dependencies = [
            task.id for task in workflow.tasks if task.status == TaskStatus.COMPLETED
        ]

        # Create task
        task_id = f"{workflow.id}_{stage}_{datetime.now(timezone.utc).timestamp()}"

        return AgentTask(
            id=task_id,
            role=role,
            objective=objective,
            context=workflow.context.copy(),
            dependencies=dependencies,
        )

    def _build_stage_objective(self, workflow: Workflow, stage: WorkflowStage) -> str:
        """Build objective for a workflow stage.

        Args:
            workflow: Parent workflow
            stage: Current stage

        Returns:
            Stage objective

        """
        base_objective = workflow.objective

        # Stage-specific objective templates
        stage_templates = {
            WorkflowStage.REQUIREMENTS: (
                f"Analyze requirements for: {base_objective}. "
                "Generate user stories, acceptance criteria, and prioritization."
            ),
            WorkflowStage.ARCHITECTURE: (
                f"Design system architecture for: {base_objective}. "
                "Define components, tech stack, APIs, and data model based on requirements."
            ),
            WorkflowStage.IMPLEMENTATION: (
                f"Implement solution for: {base_objective}. "
                "Generate production-quality code following architecture design."
            ),
            WorkflowStage.TESTING: (
                f"Create comprehensive test suite for: {base_objective}. "
                "Generate unit tests, integration tests, and test coverage strategy."
            ),
            WorkflowStage.DEPLOYMENT: (
                f"Set up deployment infrastructure for: {base_objective}. "
                "Create IaC, CI/CD pipelines, and deployment manifests."
            ),
            WorkflowStage.OPERATIONS: (
                f"Configure operations and monitoring for: {base_objective}. "
                "Set up observability, alerting, and operational runbooks."
            ),
        }

        return stage_templates.get(stage, base_objective)

    async def _execute_stage_task(self, task: AgentTask) -> AgentTask:
        """Execute a task with the appropriate agent.

        Args:
            task: Task to execute

        Returns:
            Completed task

        """
        agent = self.agents.get(task.role)
        if not agent:
            task.status = TaskStatus.FAILED
            task.error = f"No agent registered for role {task.role}"
            return task

        # Execute task with agent
        try:
            result = await agent.process_task(task)
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            return task

    async def execute_parallel_tasks(self, tasks: list[AgentTask]) -> list[AgentTask]:
        """Execute multiple tasks in parallel.

        Args:
            tasks: Tasks to execute concurrently

        Returns:
            Completed tasks

        """
        # Group tasks by role
        task_groups: dict[AgentRole, list[AgentTask]] = {}
        for task in tasks:
            if task.role not in task_groups:
                task_groups[task.role] = []
            task_groups[task.role].append(task)

        # Execute tasks concurrently
        coroutines = []
        for role, role_tasks in task_groups.items():
            agent = self.agents.get(role)
            if agent:
                for task in role_tasks:
                    coroutines.append(agent.process_task(task))

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Handle results and exceptions
        completed_tasks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tasks[i].status = TaskStatus.FAILED
                tasks[i].error = str(result)
            else:
                completed_tasks.append(result)

        return completed_tasks

    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get current status of a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow status summary

        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        return {
            "id": workflow.id,
            "name": workflow.name,
            "status": workflow.status,
            "current_stage": workflow.current_stage,
            "completed_stages": [
                task.role
                for task in workflow.tasks
                if task.status == TaskStatus.COMPLETED
            ],
            "failed_stages": [
                task.role for task in workflow.tasks if task.status == TaskStatus.FAILED
            ],
            "progress": len([t for t in workflow.tasks if t.status == TaskStatus.COMPLETED])
            / len(workflow.stages)
            if workflow.stages
            else 0.0,
            "error": workflow.error,
        }


async def create_orchestrator(
    llm_client: BaseLLMClient,
    tool_registry: ToolRegistry,
    memory: WorkingMemory | None = None,
) -> AgentOrchestrator:
    """Factory function to create and configure agent orchestrator.

    Args:
        llm_client: LLM client for agents
        tool_registry: Tool registry
        memory: Shared working memory

    Returns:
        Configured orchestrator with registered agents

    """
    from agent.agents.architecture_agent import create_architecture_agent
    from agent.agents.deployment_agent import create_deployment_agent
    from agent.agents.implementation_agent import create_implementation_agent
    from agent.agents.operations_agent import create_operations_agent
    from agent.agents.requirements_agent import create_requirements_agent
    from agent.agents.testing_agent import create_testing_agent

    orchestrator = AgentOrchestrator(llm_client, tool_registry, memory)

    # Create and register all specialized agents
    agents = {
        AgentRole.REQUIREMENTS: await create_requirements_agent(
            llm_client, tool_registry, memory
        ),
        AgentRole.ARCHITECTURE: await create_architecture_agent(
            llm_client, tool_registry, memory
        ),
        AgentRole.IMPLEMENTATION: await create_implementation_agent(
            llm_client, tool_registry, memory
        ),
        AgentRole.TESTING: await create_testing_agent(llm_client, tool_registry, memory),
        AgentRole.DEPLOYMENT: await create_deployment_agent(llm_client, tool_registry, memory),
        AgentRole.OPERATIONS: await create_operations_agent(llm_client, tool_registry, memory),
    }

    for role, agent in agents.items():
        await orchestrator.register_agent(role, agent)

    return orchestrator
