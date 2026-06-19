"""File write tool with atomic operations for safe file writing."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent.tools.base import BaseTool, ToolResult, get_tool_registry

logger = logging.getLogger(__name__)


class FileWriteInput(BaseModel):
    """Input schema for file write operations."""

    path: str = Field(..., description="Absolute or relative path to write")
    content: str = Field(..., description="Content to write to file")
    encoding: str = Field(
        default="utf-8",
        description="File encoding (utf-8, utf-16, latin-1, etc.)"
    )
    create_dirs: bool = Field(
        default=True,
        description="Create parent directories if they don't exist"
    )
    backup: bool = Field(
        default=False,
        description="Create backup of existing file before overwriting"
    )


class FileWriteTool(BaseTool):
    """Tool for writing file contents with atomic operations.

    Features:
    - Atomic writes (write to temp, then move)
    - Optional backup of existing files
    - Parent directory creation
    - Rollback on failure
    - File permissions preservation
    """

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Writes content to a file using atomic operations. "
            "Creates parent directories if needed, optionally backs up existing files, "
            "and ensures write integrity by using temporary files."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return FileWriteInput.model_json_schema()

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file write operation.

        Args:
            **kwargs: Must contain 'path' and 'content', optional params

        Returns:
            ToolResult with write confirmation or error message
        """
        try:
            # Validate and parse input
            try:
                input_data = FileWriteInput(**kwargs)
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid input: {str(e)}"
                )

            # Resolve path
            file_path = Path(input_data.path).expanduser().resolve()

            # Check if parent directory exists
            parent_dir = file_path.parent
            if not parent_dir.exists():
                if input_data.create_dirs:
                    try:
                        parent_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created parent directories: {parent_dir}")
                    except Exception as e:
                        return ToolResult(
                            success=False,
                            error=f"Failed to create parent directories: {str(e)}"
                        )
                else:
                    return ToolResult(
                        success=False,
                        error=f"Parent directory does not exist: {parent_dir}"
                    )

            # Backup existing file if requested
            backup_path = None
            if input_data.backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error=f"Failed to create backup: {str(e)}"
                    )

            # Preserve file permissions if file exists
            original_mode = None
            if file_path.exists():
                original_mode = file_path.stat().st_mode

            # Write atomically: write to temp file, then move
            result = await self._write_atomic(
                file_path=file_path,
                content=input_data.content,
                encoding=input_data.encoding,
                original_mode=original_mode
            )

            if result.success:
                # Add metadata to result
                result_data = {
                    "path": str(file_path),
                    "bytes_written": len(input_data.content.encode(input_data.encoding)),
                    "encoding": input_data.encoding
                }
                if backup_path:
                    result_data["backup_created"] = str(backup_path)

                return ToolResult(
                    success=True,
                    output=result_data
                )
            else:
                # Restore backup if write failed
                if backup_path and backup_path.exists():
                    try:
                        import shutil
                        shutil.move(str(backup_path), str(file_path))
                        logger.info("Restored backup after write failure")
                    except Exception as e:
                        logger.error(f"Failed to restore backup: {e}")
                return result

        except Exception as e:
            logger.exception("Error writing file")
            return ToolResult(
                success=False,
                error=f"Unexpected error writing file: {str(e)}"
            )

    async def _write_atomic(
        self,
        file_path: Path,
        content: str,
        encoding: str,
        original_mode: int | None = None
    ) -> ToolResult:
        """Write file atomically using temporary file.

        Args:
            file_path: Target file path
            content: Content to write
            encoding: File encoding
            original_mode: Original file permissions to preserve

        Returns:
            ToolResult with success/failure
        """
        temp_fd = None
        temp_path = None

        try:
            # Create temporary file in same directory for atomic move
            temp_fd, temp_path = tempfile.mkstemp(
                dir=file_path.parent,
                prefix=f".{file_path.name}.",
                suffix=".tmp"
            )

            # Write content to temporary file
            with os.fdopen(temp_fd, "w", encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk

            # Set permissions if we have original mode
            if original_mode:
                os.chmod(temp_path, original_mode)

            # Atomic move: replace original file
            os.replace(temp_path, str(file_path))

            logger.info(f"Successfully wrote file: {file_path}")
            return ToolResult(success=True)

        except Exception as e:
            # Clean up temp file on error
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up temp file: {cleanup_error}")

            return ToolResult(
                success=False,
                error=f"Failed to write file atomically: {str(e)}"
            )


def register_file_write_tool() -> None:
    """Register the file write tool with the global registry."""
    registry = get_tool_registry()
    registry.register(FileWriteTool())
    logger.info("Registered file write tool")
