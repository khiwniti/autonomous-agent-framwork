"""Integration tests for Phase 2 tool ecosystem."""

import pytest
import tempfile
from pathlib import Path

from agent.tools.filesystem.read import FileReadTool, register_file_read_tool
from agent.tools.filesystem.write import FileWriteTool, register_file_write_tool
from agent.tools.filesystem.search import FileSearchTool, register_file_search_tool
from agent.tools.shell.executor import ShellExecuteTool, register_shell_execute_tool
from agent.tools.git.operations import GitOperationsTool, register_git_operations_tool
from agent.tools.base import get_tool_registry


@pytest.fixture
def test_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tool_registry():
    """Create tool registry with Phase 2 tools."""
    registry = get_tool_registry()
    registry.clear()

    # Register Phase 2 tools
    register_file_read_tool()
    register_file_write_tool()
    register_file_search_tool()
    register_shell_execute_tool()
    register_git_operations_tool()

    return registry


@pytest.mark.asyncio
class TestFileSystemTools:
    """Test filesystem operation tools."""

    async def test_file_write_and_read(self, test_dir):
        """Test writing and reading a file."""
        write_tool = FileWriteTool()
        read_tool = FileReadTool()

        test_file = test_dir / "test.txt"
        content = "Hello, Phase 2!"

        # Write file
        write_result = await write_tool.execute(
            path=str(test_file),
            content=content
        )
        assert write_result.success is True
        assert test_file.exists()

        # Read file
        read_result = await read_tool.execute(path=str(test_file))
        assert read_result.success is True
        assert read_result.output["content"] == content

    async def test_file_write_atomic(self, test_dir):
        """Test atomic write operation."""
        write_tool = FileWriteTool()
        test_file = test_dir / "atomic.txt"

        # First write
        result1 = await write_tool.execute(
            path=str(test_file),
            content="Version 1"
        )
        assert result1.success is True

        # Second write should replace atomically
        result2 = await write_tool.execute(
            path=str(test_file),
            content="Version 2",
            backup=True
        )
        assert result2.success is True

        # Check backup was created
        backup_file = test_file.with_suffix(".txt.bak")
        assert backup_file.exists()

        # Verify content
        read_tool = FileReadTool()
        result = await read_tool.execute(path=str(test_file))
        assert result.output["content"] == "Version 2"

    async def test_file_search(self, test_dir):
        """Test file search with glob patterns."""
        write_tool = FileWriteTool()
        search_tool = FileSearchTool()

        # Create test files
        files = [
            "test1.py",
            "test2.py",
            "config.json",
            "subdir/nested.py"
        ]

        for file_path in files:
            full_path = test_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            await write_tool.execute(
                path=str(full_path),
                content=f"Content of {file_path}"
            )

        # Search for Python files
        result = await search_tool.execute(
            directory=str(test_dir),
            pattern="*.py",
            recursive=False
        )
        assert result.success is True
        assert result.output["count"] == 2
        assert "test1.py" in result.output["matches"]

        # Recursive search
        result_recursive = await search_tool.execute(
            directory=str(test_dir),
            pattern="**/*.py",
            recursive=True
        )
        assert result_recursive.success is True
        assert result_recursive.output["count"] == 3

    async def test_file_encoding(self, test_dir):
        """Test different file encodings."""
        write_tool = FileWriteTool()
        read_tool = FileReadTool()

        test_file = test_dir / "utf8.txt"
        content = "Hello 世界 🌍"

        # Write with UTF-8
        result = await write_tool.execute(
            path=str(test_file),
            content=content,
            encoding="utf-8"
        )
        assert result.success is True

        # Read with UTF-8
        read_result = await read_tool.execute(
            path=str(test_file),
            encoding="utf-8"
        )
        assert read_result.success is True
        assert read_result.output["content"] == content

    async def test_file_size_limit(self, test_dir):
        """Test file size limiting."""
        write_tool = FileWriteTool()
        read_tool = FileReadTool()

        test_file = test_dir / "large.txt"

        # Create large file (2MB)
        large_content = "x" * (2 * 1024 * 1024)
        await write_tool.execute(
            path=str(test_file),
            content=large_content
        )

        # Try to read with 1MB limit
        result = await read_tool.execute(
            path=str(test_file),
            max_size_mb=1
        )
        assert result.success is False
        assert "too large" in result.error.lower()


@pytest.mark.asyncio
class TestShellTool:
    """Test shell execution tool."""

    async def test_shell_simple_command(self):
        """Test simple shell command."""
        tool = ShellExecuteTool()

        result = await tool.execute(command="echo 'Hello Shell'")
        assert result.success is True
        assert "Hello Shell" in result.output["stdout"]
        assert result.output["exit_code"] == 0

    async def test_shell_with_cwd(self, test_dir):
        """Test shell command with working directory."""
        tool = ShellExecuteTool()

        result = await tool.execute(
            command="pwd",
            cwd=str(test_dir)
        )
        assert result.success is True
        assert str(test_dir) in result.output["stdout"]

    async def test_shell_timeout(self):
        """Test shell command timeout."""
        tool = ShellExecuteTool()

        result = await tool.execute(
            command="sleep 5",
            timeout=1
        )
        assert result.success is False
        assert "timed out" in result.error.lower()

    async def test_shell_error_handling(self):
        """Test shell command error handling."""
        tool = ShellExecuteTool()

        result = await tool.execute(command="exit 1")
        assert result.success is False
        assert result.output["exit_code"] == 1


@pytest.mark.asyncio
class TestGitTool:
    """Test Git operations tool."""

    @pytest.mark.skip(reason="Requires git installation and is slow")
    async def test_git_clone(self, test_dir):
        """Test Git clone operation."""
        tool = GitOperationsTool()

        repo_path = test_dir / "test-repo"
        result = await tool.execute(
            operation="clone",
            repo_path=str(repo_path),
            url="https://github.com/octocat/Hello-World.git"
        )
        assert result.success is True or "already exists" in str(result.error)

    async def test_git_status(self, test_dir):
        """Test Git status operation."""
        # Create a simple git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=test_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_dir,
            check=True
        )

        # Create and add a file
        test_file = test_dir / "test.txt"
        test_file.write_text("Initial content")

        tool = GitOperationsTool()
        result = await tool.execute(
            operation="status",
            repo_path=str(test_dir)
        )
        assert result.success is True
        assert "untracked" in result.output or "modified" in result.output


@pytest.mark.asyncio
class TestToolRegistry:
    """Test tool registry with Phase 2 tools."""

    async def test_all_tools_registered(self, tool_registry):
        """Test that all Phase 2 tools are registered."""
        tool_names = tool_registry.list_tools()

        # Check Phase 2 tools are present
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "search_files" in tool_names
        assert "shell_execute" in tool_names
        assert "git_operations" in tool_names

        # Verify we can get each tool
        for name in tool_names:
            tool = tool_registry.get(name)
            assert tool is not None
            assert tool.name == name

    async def test_openai_tool_format(self, tool_registry):
        """Test conversion to OpenAI tool format."""
        tools = tool_registry.to_openai_tools()

        assert len(tools) >= 5  # At least our Phase 2 tools

        for tool_def in tools:
            assert tool_def["type"] == "function"
            assert "function" in tool_def
            assert "name" in tool_def["function"]
            assert "description" in tool_def["function"]
            assert "parameters" in tool_def["function"]


@pytest.mark.asyncio
class TestEndToEndScenarios:
    """End-to-end integration scenarios."""

    async def test_file_workflow(self, test_dir):
        """Test complete file manipulation workflow."""
        write_tool = FileWriteTool()
        read_tool = FileReadTool()
        search_tool = FileSearchTool()

        # 1. Create multiple files
        for i in range(3):
            await write_tool.execute(
                path=str(test_dir / f"file{i}.txt"),
                content=f"Content {i}"
            )

        # 2. Search for files
        search_result = await search_tool.execute(
            directory=str(test_dir),
            pattern="*.txt"
        )
        assert search_result.output["count"] == 3

        # 3. Read each file
        for i in range(3):
            read_result = await read_tool.execute(
                path=str(test_dir / f"file{i}.txt")
            )
            assert read_result.success is True
            assert f"Content {i}" in read_result.output["content"]

        # 4. Update a file
        update_result = await write_tool.execute(
            path=str(test_dir / "file1.txt"),
            content="Updated content",
            backup=True
        )
        assert update_result.success is True

        # 5. Verify update
        verify_result = await read_tool.execute(
            path=str(test_dir / "file1.txt")
        )
        assert verify_result.output["content"] == "Updated content"
