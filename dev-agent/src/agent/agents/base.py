"""Base agent class for SDLC specialized agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.core.engine import ReActEngine
from agent.llm.base import BaseLLMClient
from agent.memory.working import WorkingMemory
from agent.tools.base import BaseTool, ToolRegistry


class AgentRole(str, Enum):
    """SDLC agent roles."""

    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    OPERATIONS = "operations"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AgentTask(BaseModel):
    """Task assigned to an agent."""

    id: str = Field(description="Unique task ID")
    role: AgentRole = Field(description="Agent role for this task")
    objective: str = Field(description="Task objective description")
    context: dict[str, Any] = Field(default_factory=dict, description="Task context")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )
    started_at: datetime | None = Field(default=None, description="Start timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    result: dict[str, Any] | None = Field(default=None, description="Task result")
    error: str | None = Field(default=None, description="Error message if failed")
    dependencies: list[str] = Field(default_factory=list, description="Dependent task IDs")


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    role: AgentRole = Field(description="Agent role")
    max_iterations: int = Field(default=25, description="Max reasoning iterations")
    timeout_seconds: int = Field(default=3600, description="Task timeout")
    enable_memory: bool = Field(default=True, description="Enable episodic memory")
    enable_learning: bool = Field(default=True, description="Enable pattern learning")
    tools: list[str] = Field(default_factory=list, description="Tool names to enable")


class BaseAgent(ABC):
    """Base class for SDLC specialized agents."""

    def __init__(
        self,
        config: AgentConfig,
        llm_client: BaseLLMClient,
        tool_registry: ToolRegistry,
        memory: WorkingMemory | None = None,
    ):
        """Initialize specialized agent.

        Args:
            config: Agent configuration
            llm_client: LLM client for reasoning
            tool_registry: Registry of available tools
            memory: Working memory for context

        """
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.memory = memory or WorkingMemory()

        # Create ReAct engine for reasoning
        self.engine = ReActEngine(
            llm_client=llm_client,
            tool_registry=tool_registry,
            max_iterations=config.max_iterations,
        )

        # Register agent-specific tools
        self._register_tools()

    def _register_tools(self) -> None:
        """Register agent-specific tools."""
        # Base implementation - override in subclasses
        pass

    @property
    @abstractmethod
    def role_description(self) -> str:
        """Human-readable description of agent's role and capabilities."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt defining agent's behavior and expertise."""
        pass

    @abstractmethod
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process a task using agent's specialized capabilities.

        Args:
            task: Task to process

        Returns:
            Updated task with results

        """
        pass

    async def execute(self, objective: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute agent task with given objective.

        Args:
            objective: Task objective description
            context: Optional task context

        Returns:
            Task execution result

        """
        # Create task
        task = AgentTask(
            id=f"{self.config.role.value}_{datetime.now(timezone.utc).timestamp()}",
            role=self.config.role,
            objective=objective,
            context=context or {},
        )

        # Process task
        result_task = await self.process_task(task)

        if result_task.status == TaskStatus.FAILED:
            raise RuntimeError(f"Task failed: {result_task.error}")

        return result_task.result or {}

    def _build_prompt(self, task: AgentTask) -> str:
        """Build prompt for agent reasoning.

        Args:
            task: Task to process

        Returns:
            Formatted prompt

        """
        prompt_parts = [
            "## Agent Role",
            self.system_prompt,
            "",
            "## Current Task",
            f"**Objective**: {task.objective}",
        ]

        if task.context:
            prompt_parts.append("")
            prompt_parts.append("## Task Context")
            for key, value in task.context.items():
                prompt_parts.append(f"**{key}**: {value}")

        if task.dependencies:
            prompt_parts.append("")
            prompt_parts.append("## Dependencies")
            prompt_parts.append(f"This task depends on: {', '.join(task.dependencies)}")

        prompt_parts.append("")
        prompt_parts.append("## Instructions")
        prompt_parts.append(
            "Analyze the task, plan your approach, execute using available tools, "
            "and provide comprehensive results. Use ReAct reasoning to break down "
            "the problem and validate your solution."
        )

        return "\n".join(prompt_parts)

    async def validate_task(self, task: AgentTask) -> tuple[bool, str | None]:
        """Validate task before processing.

        Args:
            task: Task to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        # Check role match
        if task.role != self.config.role:
            return False, f"Task role {task.role} doesn't match agent role {self.config.role}"

        # Check dependencies
        if task.dependencies:
            # In production, check if dependencies are completed
            # For now, just validate they exist
            pass

        return True, None

    def _extract_deliverables(self, result: str) -> dict[str, Any]:
        """Extract structured deliverables from agent output.

        Args:
            result: Agent output text

        Returns:
            Structured deliverables

        """
        # Base implementation - override in subclasses for specific extraction
        return {
            "output": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_role": self.config.role.value,
        }


class AgentCapability(BaseModel):
    """Agent capability definition."""

    name: str = Field(description="Capability name")
    description: str = Field(description="What this capability enables")
    tools_required: list[str] = Field(default_factory=list, description="Required tools")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence level")


def create_agent_config(
    role: AgentRole,
    max_iterations: int = 25,
    timeout_seconds: int = 3600,
    tools: list[str] | None = None,
) -> AgentConfig:
    """Factory function to create agent configuration.

    Args:
        role: Agent role
        max_iterations: Max reasoning iterations
        timeout_seconds: Task timeout
        tools: Tool names to enable

    Returns:
        Agent configuration

    """
    return AgentConfig(
        role=role,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        tools=tools or [],
    )
