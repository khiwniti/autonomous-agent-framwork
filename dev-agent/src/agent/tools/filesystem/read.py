"""File read tool for reading files with encoding detection."""

import logging
import mimetypes
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent.tools.base import BaseTool, ToolResult, get_tool_registry

logger = logging.getLogger(__name__)


class FileReadInput(BaseModel):
    """Input schema for file read operations."""

    path: str = Field(..., description="Absolute or relative path to file")
    encoding: str | None = Field(
        default=None,
        description="File encoding (utf-8, utf-16, latin-1, etc.). Auto-detected if not provided."
    )
    max_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum file size in MB to read (prevents memory issues)"
    )


class FileReadTool(BaseTool):
    """Tool for reading file contents with encoding support.

    Features:
    - Automatic encoding detection
    - Binary file handling
    - Size limiting for safety
    - Error handling with detailed messages
    """

    COMMON_ENCODINGS = ["utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1", "cp1252"]

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Reads contents of a file with automatic encoding detection. "
            "Supports text files (source code, configs, docs) and provides "
            "detailed error messages for binary or unreadable files."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return FileReadInput.model_json_schema()

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute file read operation.

        Args:
            **kwargs: Must contain 'path', optional 'encoding' and 'max_size_mb'

        Returns:
            ToolResult with file contents or error message
        """
        try:
            # Validate and parse input
            try:
                input_data = FileReadInput(**kwargs)
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid input: {str(e)}"
                )

            # Resolve path
            file_path = Path(input_data.path).expanduser().resolve()

            # Security check: file must exist and be a file
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path}"
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {file_path}"
                )

            # Size check
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > input_data.max_size_mb:
                return ToolResult(
                    success=False,
                    error=(
                        f"File too large: {size_mb:.2f}MB exceeds limit of "
                        f"{input_data.max_size_mb}MB"
                    )
                )

            # Check if file is likely binary
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type and not mime_type.startswith("text/"):
                # Allow some common text-based mimes
                allowed_binary_types = [
                    "application/json",
                    "application/xml",
                    "application/javascript",
                ]
                if mime_type not in allowed_binary_types:
                    return ToolResult(
                        success=False,
                        error=(
                            f"File appears to be binary ({mime_type}). "
                            "This tool only reads text files."
                        )
                    )

            # Try to read with specified encoding or auto-detect
            if input_data.encoding:
                content = await self._read_with_encoding(
                    file_path, input_data.encoding
                )
            else:
                content = await self._read_with_auto_detect(file_path)

            return ToolResult(
                success=True,
                output={
                    "path": str(file_path),
                    "content": content,
                    "size_bytes": file_path.stat().st_size,
                    "size_mb": f"{size_mb:.2f}"
                }
            )

        except Exception as e:
            logger.exception("Error reading file")
            return ToolResult(
                success=False,
                error=f"Unexpected error reading file: {str(e)}"
            )

    async def _read_with_encoding(self, file_path: Path, encoding: str) -> str:
        """Read file with specific encoding.

        Args:
            file_path: Path to file
            encoding: Encoding to use

        Returns:
            File contents as string

        Raises:
            UnicodeDecodeError: If encoding doesn't match file
            IOError: If file can't be read
        """
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(
                e.encoding,
                e.object,
                e.start,
                e.end,
                f"Failed to decode with {encoding}: {e.reason}"
            )

    async def _read_with_auto_detect(self, file_path: Path) -> str:
        """Read file with automatic encoding detection.

        Tries common encodings in order until successful.

        Args:
            file_path: Path to file

        Returns:
            File contents as string

        Raises:
            UnicodeDecodeError: If no encoding works
        """
        errors = []

        for encoding in self.COMMON_ENCODINGS:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                logger.debug(f"Successfully read {file_path} with {encoding}")
                return content
            except UnicodeDecodeError as e:
                errors.append(f"{encoding}: {e.reason}")
                continue

        # If all encodings failed, try binary read for more info
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(100)

            raise UnicodeDecodeError(
                "utf-8",
                first_bytes,
                0,
                len(first_bytes),
                (
                    f"Could not decode file with any common encoding. "
                    f"Tried: {', '.join(self.COMMON_ENCODINGS)}. "
                    f"Errors: {'; '.join(errors)}. "
                    "File may be binary or use an uncommon encoding."
                )
            )
        except Exception as e:
            raise IOError(f"Could not read file: {str(e)}")


def register_file_read_tool() -> None:
    """Register the file read tool with the global registry."""
    registry = get_tool_registry()
    registry.register(FileReadTool())
    logger.info("Registered file read tool")
