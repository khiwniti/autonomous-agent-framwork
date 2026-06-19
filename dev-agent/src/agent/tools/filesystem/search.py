"""File search tool for finding files by patterns"""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent.tools.base import BaseTool, ToolResult, get_tool_registry

logger = logging.getLogger(__name__)


class FileSearchInput(BaseModel):
    """Input schema for file search operations."""

    directory: str = Field(..., description="Directory to search in (absolute or relative)")
    pattern: str = Field(
        default="*",
        description="Glob pattern to match files (e.g., '*.py', '**/*.txt', 'test_*.py')"
    )
    recursive: bool = Field(
        default=True,
        description="Search subdirectories recursively"
    )
    include_hidden: bool = Field(
        default=False,
        description="Include hidden files (starting with .)"
    )
    file_type: str | None = Field(
        default=None,
        description="Filter by type: 'file', 'dir', or None for both"
    )
    max_results: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of results to return"
    )


class FileSearchTool(BaseTool):
    """Tool for searching files using glob patterns.

    Features:
    - Glob pattern matching (*, **, ?, [])
    - Recursive and non-recursive search
    - File type filtering (files vs directories)
    - Hidden file handling
    Result limiting
    """

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            "Searches for files and directories using glob patterns. "
            "Supports wildcards (**/*, ?, []) and can filter by file type. "
            "Use ** for recursive search across all subdirectories."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return FileSearchInput.model_json_schema()

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file search operation.

        Args:
            **kwargs: Must contain 'directory', optional pattern and filters

        Returns:
            ToolResult with list of matching file paths
        """
        try:
            # Validate and parse input
            try:
                input_data = FileSearchInput(**kwargs)
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid input: {str(e)}"
                )

            # Resolve directory path
            search_dir = Path(input_data.directory).expanduser().resolve()

            # Validate directory exists
            if not search_dir.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {search_dir}"
                )

            if not search_dir.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {search_dir}"
                )

            # Perform search
            matches = await self._search_files(
                directory=search_dir,
                pattern=input_data.pattern,
                recursive=input_data.recursive,
                include_hidden=input_data.include_hidden,
                file_type=input_data.file_type,
                max_results=input_data.max_results
            )

            # Format results
            result_data = {
                "directory": str(search_dir),
                "pattern": input_data.pattern,
                "count": len(matches),
                "matches": [str(p.relative_to(search_dir)) for p in matches]
            }

            if len(matches) >= input_data.max_results:
                result_data["warning"] = f"Results truncated at {input_data.max_results}"

            return ToolResult(
                success=True,
                output=result_data
            )

        except Exception as e:
            logger.exception("Error searching files")
            return ToolResult(
                success=False,
                error=f"Unexpected error searching files: {str(e)}"
            )

    async def _search_files(
        self,
        directory: Path,
        pattern: str,
        recursive: bool,
        include_hidden: bool,
        file_type: str | None,
        max_results: int
    ) -> list[Path]:
        """Search for files matching pattern.

        Args:
            directory: Directory to search in
            pattern: Glob pattern
            recursive: Whether to search recursively
            include_hidden: Whether to include hidden files
            file_type: Filter by 'file', 'dir', or None
            max_results: Maximum results to return

        Returns:
            List of matching paths
        """
        matches = []

        try:
            # Use rglob for recursive, glob for non-recursive
            if recursive:
                search_results = directory.rglob(pattern)
            else:
                search_results = directory.glob(pattern)

            for path in search_results:
                # Check if we've hit the limit
                if len(matches) >= max_results:
                    break

                # Filter hidden files
                if not include_hidden and any(
                    part.startswith(".") for part in path.relative_to(directory).parts
                ):
                    continue

                # Filter by file type
                if file_type == "file" and not path.is_file():
                    continue
                if file_type == "dir" and not path.is_dir():
                    continue

                matches.append(path)

        except Exception as e:
            logger.error(f"Error during glob search: {e}")
            raise

        return matches


def register_file_search_tool() -> None:
    """Register the file search tool with the global registry."""
    registry = get_tool_registry()
    registry.register(FileSearchTool())
    logger.info("Registered file search tool")
