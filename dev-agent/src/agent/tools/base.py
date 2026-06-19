"""Base tool interface and registry for agent execution."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result from tool execution."""

    success: bool = Field(description="Whether execution succeeded")
    output: Any = Field(default=None, description="Tool output")
    error: str | None = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""

    def __init__(self, message: str, tool_name: str, original_error: Exception | None = None):
        """Initialize tool execution error.

        Args:
            message: Error message
            tool_name: Name of the tool that failed
            original_error: Original exception if any
        """
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' failed: {message}")


@dataclass
class ToolParameter:
    """Tool parameter definition."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self) -> None:
        """Initialize tool."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name.

        Returns:
            Unique tool identifier
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description.

        Returns:
            Human-readable description of what the tool does
        """
        pass

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters.

        Returns:
            List of parameter definitions
        """
        return []

    @property
    def requires_sandbox(self) -> bool:
        """Whether tool requires sandbox execution.

        Returns:
            True if tool should run in sandbox, False otherwise
        """
        return False

    @property
    def permissions(self) -> list[str]:
        """Permissions required by tool.

        Returns:
            List of permission identifiers
        """
        return []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result

        Raises:
            ToolExecutionError: If execution fails
        """
        pass

    def validate_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate and prepare inputs.

        Args:
            inputs: Raw input parameters

        Returns:
            Validated and prepared inputs

        Raises:
            ValueError: If validation fails
        """
        validated: dict[str, Any] = {}

        # Check required parameters
        for param in self.parameters:
            if param.required and param.name not in inputs:
                raise ValueError(f"Missing required parameter: {param.name}")

            # Use default if not provided
            if param.name not in inputs and param.default is not None:
                validated[param.name] = param.default
            elif param.name in inputs:
                validated[param.name] = inputs[param.name]

        return validated

    def validate_output(self, result: Any) -> Any:
        """Validate tool output.

        Args:
            result: Raw output from tool

        Returns:
            Validated output

        Raises:
            ValueError: If validation fails
        """
        return result

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert tool to OpenAI function calling format.

        Returns:
            OpenAI tool definition
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool.

        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name in self._tools:
            del self._tools[tool_name]

    def get(self, tool_name: str) -> BaseTool | None:
        """Get tool by name.

        Args:
            tool_name: Name of tool to retrieve

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)

    def list_tools(self) -> list[str]:
        """List all registered tools.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function calling format.

        Returns:
            List of OpenAI tool definitions
        """
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()


# Global tool registry instance
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get global tool registry instance.

    Returns:
        Singleton ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
