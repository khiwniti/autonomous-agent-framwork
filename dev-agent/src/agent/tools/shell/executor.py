"""Shell execution tool for running commands."""

import asyncio
import logging
import subprocess
from typing import Any

from pydantic import BaseModel, Field

from agent.tools.base import BaseTool, ToolResult, get_tool_registry

logger = logging.getLogger(__name__)


class ShellExecuteInput(BaseModel):
    """Input schema for shell execution."""

    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")
    cwd: str | None = Field(default=None, description="Working directory")


class ShellExecuteTool(BaseTool):
    """Execute shell commands with timeout and output capture."""

    @property
    def name(self) -> str:
        return "shell_execute"

    @property
    def description(self) -> str:
        return "Executes shell commands safely with timeout. Returns stdout, stderr, and exit code."

    @property
    def input_schema(self) -> dict[str, Any]:
        return ShellExecuteInput.model_json_schema()

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute shell command."""
        try:
            input_data = ShellExecuteInput(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid input: {e}")

        try:
            process = await asyncio.create_subprocess_shell(
                input_data.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=input_data.cwd
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=input_data.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {input_data.timeout}s"
                )

            return ToolResult(
                success=process.returncode == 0,
                output={
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "exit_code": process.returncode
                },
                error=None if process.returncode == 0 else f"Exit code: {process.returncode}"
            )

        except Exception as e:
            logger.exception("Shell execution error")
            return ToolResult(success=False, error=f"Execution failed: {e}")


def register_shell_execute_tool() -> None:
    """Register shell execution tool."""
    get_tool_registry().register(ShellExecuteTool())
    logger.info("Registered shell execute tool")
