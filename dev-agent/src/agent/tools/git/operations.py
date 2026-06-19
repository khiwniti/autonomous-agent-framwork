"""Git operations tool."""

import logging
from pathlib import Path
from typing import Any

from git import Repo
from pydantic import BaseModel, Field

from agent.tools.base import BaseTool, ToolResult, get_tool_registry

logger = logging.getLogger(__name__)


class GitOperationInput(BaseModel):
    """Input schema for Git operations."""

    operation: str = Field(..., description="Git operation: clone, status, diff, log, commit, push, pull")
    repo_path: str = Field(..., description="Path to git repository")
    url: str | None = Field(default=None, description="Git URL (for clone)")
    message: str | None = Field(default=None, description="Commit message")
    branch: str | None = Field(default=None, description="Branch name")


class GitOperationsTool(BaseTool):
    """Perform Git operations on repositories."""

    @property
    def name(self) -> str:
        return "git_operations"

    @property
    def description(self) -> str:
        return "Perform Git operations: clone, status, diff, log, commit, push, pull"

    @property
    def input_schema(self) -> dict[str, Any]:
        return GitOperationInput.model_json_schema()

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute Git operation."""
        try:
            input_data = GitOperationInput(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid input: {e}")

        try:
            op = input_data.operation.lower()

            if op == "clone":
                if not input_data.url:
                    return ToolResult(success=False, error="URL required for clone")
                repo = Repo.clone_from(input_data.url, input_data.repo_path)
                return ToolResult(success=True, output={"cloned_to": input_data.repo_path})

            # For other operations, repo must exist
            repo_path = Path(input_data.repo_path).expanduser().resolve()
            if not repo_path.exists():
                return ToolResult(success=False, error=f"Repository not found: {repo_path}")

            repo = Repo(repo_path)

            if op == "status":
                return ToolResult(success=True, output={
                    "branch": repo.active_branch.name,
                    "modified": [item.a_path for item in repo.index.diff(None)],
                    "untracked": repo.untracked_files
                })

            elif op == "diff":
                diff_text = repo.git.diff()
                return ToolResult(success=True, output={"diff": diff_text})

            elif op == "log":
                commits = list(repo.iter_commits(max_count=10))
                log_data = [
                    {
                        "hash": str(commit.hexsha[:8]),
                        "author": str(commit.author),
                        "date": str(commit.committed_datetime),
                        "message": commit.message.strip()
                    }
                    for commit in commits
                ]
                return ToolResult(success=True, output={"commits": log_data})

            elif op == "commit":
                if not input_data.message:
                    return ToolResult(success=False, error="Message required for commit")
                repo.git.add(A=True)
                repo.index.commit(input_data.message)
                return ToolResult(success=True, output={"committed": input_data.message})

            elif op == "push":
                origin = repo.remote(name="origin")
                origin.push()
                return ToolResult(success=True, output={"pushed": "origin"})

            elif op == "pull":
                origin = repo.remote(name="origin")
                origin.pull()
                return ToolResult(success=True, output={"pulled": "origin"})

            else:
                return ToolResult(success=False, error=f"Unknown operation: {op}")

        except Exception as e:
            logger.exception(f"Git operation {input_data.operation} failed")
            return ToolResult(success=False, error=f"Git operation failed: {e}")


def register_git_operations_tool() -> None:
    """Register Git operations tool."""
    get_tool_registry().register(GitOperationsTool())
    logger.info("Registered Git operations tool")
