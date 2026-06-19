"""ReAct reasoning engine implementation.

Implements the ReAct (Reasoning + Acting) pattern for autonomous task execution:
1. Plan: Generate action plan based on task
2. Execute: Run tools and collect results
3. Reflect: Evaluate progress and decide next steps
4. Learn: Extract patterns for future tasks
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jinja2 import Template

from agent.config.settings import get_settings
from agent.llm.base import LLMGenerationConfig, LLMMessage
from agent.llm.openai_client import OpenAIClient
from agent.tools.base import ToolRegistry, get_tool_registry

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent execution state."""

    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionStep:
    """Single step in agent execution."""

    iteration: int
    state: AgentState
    thought: str
    action: str | None = None
    action_input: dict[str, Any] | None = None
    observation: str | None = None
    error: str | None = None
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


@dataclass
class ExecutionResult:
    """Result of agent execution."""

    success: bool
    output: str
    steps: list[ExecutionStep]
    iterations: int
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ReActEngine:
    """ReAct reasoning engine for autonomous task execution.

    Implements multi-step reasoning loop with planning, execution, and reflection.
    """

    # Prompt templates
    SYSTEM_PROMPT = """You are an autonomous AI agent specialized in software development tasks. You have access to various tools to help you complete tasks.

Your capabilities:
- Analyze requirements and plan solutions
- Execute code and shell commands
- Search and modify files
- Use Git for version control
- Browse the web for information
- Parse and analyze code

You must use the ReAct (Reasoning + Acting) approach:
1. **Thought**: Think about what needs to be done
2. **Action**: Choose and execute a tool
3. **Observation**: Analyze the tool's output
4. **Reflection**: Evaluate progress every 5 steps

Always break complex tasks into smaller steps. Be methodical and verify your work."""

    PLANNING_PROMPT = Template("""Task: {{ task }}

Available tools:
{% for tool in tools %}
- **{{ tool.name }}**: {{ tool.description }}
{% endfor %}

Current progress:
{{ progress }}

Think step-by-step about how to accomplish this task. What should you do next?

Respond in this format:
Thought: [your reasoning about what to do next]
Action: [tool name to use, or "finish" if task is complete]
Action Input: [JSON object with tool parameters, or final result if finishing]""")

    REFLECTION_PROMPT = Template("""You have completed {{ num_steps }} steps. Let's reflect on progress:

Original task: {{ task }}

Steps taken so far:
{% for step in recent_steps %}
{{ loop.index }}. {{ step.action }}: {{ step.observation[:200] }}...
{% endfor %}

Questions to consider:
1. Am I making progress toward the goal?
2. Have I tried the same action repeatedly without success?
3. Do I need to adjust my approach?
4. Should I continue or mark task as complete?

Provide honest assessment of progress and next steps.""")

    def __init__(
        self,
        llm_client: OpenAIClient | None = None,
        tool_registry: ToolRegistry | None = None,
        max_iterations: int | None = None,
        reflection_interval: int | None = None,
    ) -> None:
        """Initialize ReAct engine.

        Args:
            llm_client: LLM client for generation (defaults to new OpenAIClient)
            tool_registry: Tool registry (defaults to global registry)
            max_iterations: Max reasoning loop iterations (defaults to settings)
            reflection_interval: Steps between reflection (defaults to settings)
        """
        settings = get_settings()

        self.llm_client = llm_client or OpenAIClient()
        self.tool_registry = tool_registry or get_tool_registry()
        self.max_iterations = max_iterations or settings.agent_max_iterations
        self.reflection_interval = reflection_interval or settings.agent_reflection_interval

        self.state = AgentState.IDLE
        self.steps: list[ExecutionStep] = []
        self.action_history: list[str] = []

    async def execute(self, task: str) -> ExecutionResult:
        """Execute task using ReAct reasoning loop.

        Args:
            task: Task description to accomplish

        Returns:
            Execution result with output and steps
        """
        logger.info(f"Starting ReAct execution for task: {task}")
        self.state = AgentState.PLANNING
        self.steps = []
        self.action_history = []

        settings = get_settings()
        model = settings.llm_model
        temperature = settings.llm_temperature

        try:
            for iteration in range(1, self.max_iterations + 1):
                logger.debug(f"ReAct iteration {iteration}/{self.max_iterations}")

                # Check for infinite loops
                if self._detect_loop():
                    error_msg = "Detected infinite loop - same actions repeating"
                    logger.warning(error_msg)
                    return ExecutionResult(
                        success=False,
                        output="",
                        steps=self.steps,
                        iterations=iteration,
                        error=error_msg,
                    )

                # Reflection checkpoint
                if iteration % self.reflection_interval == 0:
                    await self._reflect(task, iteration)

                # Generate next action
                self.state = AgentState.PLANNING
                thought, action, action_input = await self._plan_next_action(
                    task, model, temperature
                )

                step = ExecutionStep(
                    iteration=iteration,
                    state=AgentState.PLANNING,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                )
                self.steps.append(step)

                # Check if finished
                if action.lower() == "finish":
                    logger.info(f"Task completed in {iteration} iterations")
                    return ExecutionResult(
                        success=True,
                        output=action_input.get("result", "Task completed"),
                        steps=self.steps,
                        iterations=iteration,
                    )

                # Execute action
                self.state = AgentState.EXECUTING
                step.state = AgentState.EXECUTING

                try:
                    observation = await self._execute_action(action, action_input)
                    step.observation = observation
                    self.action_history.append(action)

                except Exception as e:
                    error_msg = f"Action execution failed: {str(e)}"
                    logger.error(error_msg)
                    step.error = error_msg
                    step.observation = error_msg

            # Max iterations reached
            error_msg = f"Max iterations ({self.max_iterations}) reached without completion"
            logger.warning(error_msg)
            return ExecutionResult(
                success=False,
                output="",
                steps=self.steps,
                iterations=self.max_iterations,
                error=error_msg,
            )

        except Exception as e:
            logger.exception("ReAct execution failed")
            return ExecutionResult(
                success=False,
                output="",
                steps=self.steps,
                iterations=len(self.steps),
                error=str(e),
            )
        finally:
            self.state = AgentState.IDLE

    async def _plan_next_action(
        self, task: str, model: str, temperature: float
    ) -> tuple[str, str, dict[str, Any]]:
        """Generate next action using LLM.

        Args:
            task: Original task description
            model: LLM model to use
            temperature: Sampling temperature

        Returns:
            Tuple of (thought, action_name, action_input)
        """
        # Build progress summary
        progress = self._build_progress_summary()

        # Get available tools
        tools = list(self.tool_registry._tools.values())

        # Render prompt
        user_message = self.PLANNING_PROMPT.render(
            task=task,
            tools=tools,
            progress=progress,
        )

        messages = [
            LLMMessage(role="system", content=self.SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_message),
        ]

        # Generate response
        config = LLMGenerationConfig(
            model=model,
            temperature=temperature,
            max_tokens=1000,
        )

        response = await self.llm_client.generate(messages, config)
        content = response.content

        # Parse response
        thought, action, action_input = self._parse_react_response(content)

        return thought, action, action_input

    async def _execute_action(
        self, action: str, action_input: dict[str, Any]
    ) -> str:
        """Execute tool action.

        Args:
            action: Tool name to execute
            action_input: Tool parameters

        Returns:
            Observation from tool execution

        Raises:
            Exception: If tool execution fails
        """
        tool = self.tool_registry.get(action)

        if tool is None:
            available = ", ".join(self.tool_registry.list_tools())
            raise ValueError(
                f"Unknown tool '{action}'. Available tools: {available}"
            )

        logger.info(f"Executing tool: {action}")
        result = await tool.execute(**action_input)

        if result.success:
            # Truncate long outputs
            output_str = str(result.output)
            if len(output_str) > 500:
                output_str = output_str[:500] + "... (truncated)"
            return output_str
        else:
            raise Exception(result.error or "Tool execution failed")

    async def _reflect(self, task: str, iteration: int) -> None:
        """Perform reflection on progress.

        Args:
            task: Original task
            iteration: Current iteration number
        """
        logger.debug(f"Performing reflection at iteration {iteration}")
        self.state = AgentState.REFLECTING

        recent_steps = self.steps[-self.reflection_interval :]

        reflection_message = self.REFLECTION_PROMPT.render(
            task=task,
            num_steps=len(self.steps),
            recent_steps=recent_steps,
        )

        messages = [
            LLMMessage(role="system", content=self.SYSTEM_PROMPT),
            LLMMessage(role="user", content=reflection_message),
        ]

        config = LLMGenerationConfig(
            model=get_settings().llm_model,
            temperature=0.7,
            max_tokens=500,
        )

        response = await self.llm_client.generate(messages, config)
        reflection = response.content

        # Store reflection
        step = ExecutionStep(
            iteration=iteration,
            state=AgentState.REFLECTING,
            thought=reflection,
        )
        self.steps.append(step)

        logger.info(f"Reflection: {reflection[:200]}...")

    def _detect_loop(self) -> bool:
        """Detect infinite loops in action history.

        Returns:
            True if loop detected, False otherwise
        """
        if len(self.action_history) < 6:
            return False

        # Check last 6 actions for pattern
        recent = self.action_history[-6:]

        # Simple pattern: AAA or ABABAB
        if len(set(recent)) == 1:
            logger.warning(f"Loop detected: repeated action '{recent[0]}'")
            return True

        if len(set(recent)) == 2 and recent[0] == recent[2] == recent[4]:
            logger.warning(f"Loop detected: alternating pattern {recent[0]}/{recent[1]}")
            return True

        return False

    def _build_progress_summary(self) -> str:
        """Build summary of progress so far.

        Returns:
            Progress summary string
        """
        if not self.steps:
            return "No steps taken yet."

        summary_parts = []
        for i, step in enumerate(self.steps[-5:], start=1):  # Last 5 steps
            if step.action and step.observation:
                summary_parts.append(
                    f"{i}. {step.action}: {step.observation[:100]}..."
                )

        return "\n".join(summary_parts) if summary_parts else "No actions yet."

    def _parse_react_response(self, content: str) -> tuple[str, str, dict[str, Any]]:
        """Parse ReAct format response from LLM.

        Args:
            content: LLM response content

        Returns:
            Tuple of (thought, action, action_input)
        """
        thought = ""
        action = ""
        action_input: dict[str, Any] = {}

        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()

            if line.startswith("Thought:"):
                thought = line.replace("Thought:", "").strip()
            elif line.startswith("Action:"):
                action = line.replace("Action:", "").strip()
            elif line.startswith("Action Input:"):
                input_str = line.replace("Action Input:", "").strip()
                try:
                    action_input = json.loads(input_str)
                except json.JSONDecodeError:
                    # Fallback: treat as simple string
                    action_input = {"input": input_str}

        # Defaults if parsing failed
        if not action:
            action = "finish"
            action_input = {"result": content}

        return thought, action, action_input

    async def close(self) -> None:
        """Close engine and release resources."""
        if self.llm_client:
            await self.llm_client.close()
