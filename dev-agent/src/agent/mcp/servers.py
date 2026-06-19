"""MCP Server Configurations for SDLC Phases.

This module provides factory functions for creating MCP server configurations
for each SDLC phase, mapping to the official MCP servers and community servers.

SDLC Phase -> MCP Servers mapping:
- Code editing: Filesystem (@modelcontextprotocol/server-filesystem)
- Version control: Git (@modelcontextprotocol/server-git)
- Code hosting: GitHub (ghcr.io/github/github-mcp-server)
- Database: PostgreSQL (@modelcontextprotocol/server-postgres)
- Browser testing: Puppeteer/Playwright (mcp/puppeteer)
- Container management: Docker (community)
- Kubernetes deployment: Kubernetes (containers/kubernetes-mcp-server)
- Shell execution: Terminal (community)
- Agent memory: Knowledge graph (@modelcontextprotocol/server-memory)
- Web research: Fetch (@modelcontextprotocol/server-fetch)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MCPServerType(str, Enum):
    """Supported MCP server types."""
    
    FILESYSTEM = "filesystem"
    GIT = "git"
    GITHUB = "github"
    POSTGRES = "postgres"
    SQLITE = "sqlite"
    PUPPETEER = "puppeteer"
    PLAYWRIGHT = "playwright"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    SHELL = "shell"
    MEMORY = "memory"
    FETCH = "fetch"


@dataclass
class MCPServerConfig:
    """MCP server configuration."""
    
    name: str
    server_type: MCPServerType
    transport: str  # "stdio" or "streamable_http"
    
    # stdio options
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    
    # HTTP options
    url: str | None = None
    headers: dict[str, str] | None = None
    
    # Server-specific options
    options: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for MultiServerMCPClient."""
        config = {"transport": self.transport}
        
        if self.transport == "stdio":
            config["command"] = self.command
            if self.args:
                config["args"] = self.args
            if self.env:
                config["env"] = self.env
        else:
            config["url"] = self.url
            if self.headers:
                config["headers"] = self.headers
        
        return config


# ============================================================================
# Factory Functions for SDLC MCP Servers
# ============================================================================

def create_filesystem_server(
    workspace_path: str,
    allowed_paths: list[str] | None = None,
    read_only: bool = False,
) -> MCPServerConfig:
    """
    Create filesystem MCP server configuration.
    
    Provides: read_file, write_file, list_directory, create_directory,
              delete_file, move_file, search_files
    
    Args:
        workspace_path: Root workspace path for file operations
        allowed_paths: Additional allowed paths (optional)
        read_only: If True, disable write operations
        
    Returns:
        MCP server configuration
    """
    args = ["-y", "@modelcontextprotocol/server-filesystem", workspace_path]
    
    if allowed_paths:
        args.extend(allowed_paths)
    
    return MCPServerConfig(
        name="filesystem",
        server_type=MCPServerType.FILESYSTEM,
        transport="stdio",
        command="npx",
        args=args,
        options={"read_only": read_only},
    )


def create_git_server(
    repo_path: str | None = None,
) -> MCPServerConfig:
    """
    Create Git MCP server configuration.
    
    Provides: git_status, git_diff, git_commit, git_add, git_log,
              git_branch, git_checkout, git_push, git_pull
    
    Args:
        repo_path: Git repository path (defaults to current directory)
        
    Returns:
        MCP server configuration
    """
    args = ["-y", "@modelcontextprotocol/server-git"]
    
    if repo_path:
        args.extend(["--repo", repo_path])
    
    return MCPServerConfig(
        name="git",
        server_type=MCPServerType.GIT,
        transport="stdio",
        command="npx",
        args=args,
    )


def create_github_server(
    token: str | None = None,
    dynamic_toolsets: bool = True,
) -> MCPServerConfig:
    """
    Create GitHub MCP server configuration.
    
    Provides: create_issue, create_pull_request, list_issues,
              search_code, get_file_contents, create_branch
    
    The --dynamic-toolsets flag enables LLM-driven tool discovery
    to avoid context window bloat.
    
    Args:
        token: GitHub personal access token (or set GITHUB_TOKEN env)
        dynamic_toolsets: Enable dynamic tool loading
        
    Returns:
        MCP server configuration
    """
    env = {}
    if token:
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
    
    args = []
    if dynamic_toolsets:
        args.append("--dynamic-toolsets")
    
    # For local development, use stdio
    # For production, use the container image via HTTP
    return MCPServerConfig(
        name="github",
        server_type=MCPServerType.GITHUB,
        transport="stdio",
        command="docker",
        args=["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
              "ghcr.io/github/github-mcp-server"] + args,
        env=env,
    )


def create_github_server_http(
    url: str = "http://github-mcp:8001/mcp",
    token: str | None = None,
) -> MCPServerConfig:
    """Create GitHub MCP server for HTTP transport (production)."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    return MCPServerConfig(
        name="github",
        server_type=MCPServerType.GITHUB,
        transport="streamable_http",
        url=url,
        headers=headers,
    )


def create_database_server(
    db_type: str = "postgres",
    connection_string: str | None = None,
) -> MCPServerConfig:
    """
    Create database MCP server configuration.
    
    Provides: query, execute, list_tables, describe_table, list_schemas
    
    Args:
        db_type: Database type ("postgres" or "sqlite")
        connection_string: Database connection string
        
    Returns:
        MCP server configuration
    """
    if db_type == "postgres":
        return MCPServerConfig(
            name="database",
            server_type=MCPServerType.POSTGRES,
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres", connection_string or ""],
        )
    elif db_type == "sqlite":
        return MCPServerConfig(
            name="database",
            server_type=MCPServerType.SQLITE,
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-sqlite", connection_string or ""],
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def create_browser_server(
    browser_type: str = "puppeteer",
    headless: bool = True,
) -> MCPServerConfig:
    """
    Create browser automation MCP server configuration.
    
    Provides: navigate, click, type_text, screenshot, get_text,
              wait_for_element, evaluate_script
    
    Args:
        browser_type: "puppeteer" or "playwright"
        headless: Run browser in headless mode
        
    Returns:
        MCP server configuration
    """
    if browser_type == "puppeteer":
        return MCPServerConfig(
            name="browser",
            server_type=MCPServerType.PUPPETEER,
            transport="stdio",
            command="npx",
            args=["-y", "@anthropic/mcp-server-puppeteer"],
            options={"headless": headless},
        )
    elif browser_type == "playwright":
        return MCPServerConfig(
            name="browser",
            server_type=MCPServerType.PLAYWRIGHT,
            transport="stdio",
            command="npx",
            args=["-y", "playwright-mcp-server"],
            options={"headless": headless},
        )
    else:
        raise ValueError(f"Unsupported browser type: {browser_type}")


def create_docker_server() -> MCPServerConfig:
    """
    Create Docker MCP server configuration.
    
    Provides: docker_build, docker_run, docker_stop, docker_logs,
              docker_ps, docker_images, docker_pull
              
    Returns:
        MCP server configuration
    """
    return MCPServerConfig(
        name="docker",
        server_type=MCPServerType.DOCKER,
        transport="stdio",
        command="docker-mcp-server",  # Community server
        args=[],
    )


def create_kubernetes_server(
    kubeconfig: str | None = None,
    namespace: str = "default",
) -> MCPServerConfig:
    """
    Create Kubernetes MCP server configuration.
    
    Provides: kubectl_get, kubectl_apply, kubectl_delete,
              kubectl_logs, kubectl_exec, kubectl_describe
    
    Args:
        kubeconfig: Path to kubeconfig file
        namespace: Default Kubernetes namespace
        
    Returns:
        MCP server configuration
    """
    env = {"KUBERNETES_NAMESPACE": namespace}
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig
    
    return MCPServerConfig(
        name="kubernetes",
        server_type=MCPServerType.KUBERNETES,
        transport="stdio",
        command="kubernetes-mcp-server",  # containers/kubernetes-mcp-server
        args=[],
        env=env,
    )


def create_shell_server(
    working_dir: str | None = None,
    allowed_commands: list[str] | None = None,
) -> MCPServerConfig:
    """
    Create shell execution MCP server configuration.
    
    Provides: execute_command, run_script
    
    Args:
        working_dir: Default working directory
        allowed_commands: List of allowed commands (security)
        
    Returns:
        MCP server configuration
    """
    args = []
    if working_dir:
        args.extend(["--working-dir", working_dir])
    if allowed_commands:
        args.extend(["--allowed-commands", ",".join(allowed_commands)])
    
    return MCPServerConfig(
        name="shell",
        server_type=MCPServerType.SHELL,
        transport="stdio",
        command="shell-mcp-server",
        args=args,
    )


def create_memory_server() -> MCPServerConfig:
    """
    Create memory/knowledge graph MCP server configuration.
    
    Provides: store_memory, retrieve_memory, search_memories,
              create_entity, create_relation, query_graph
              
    Returns:
        MCP server configuration
    """
    return MCPServerConfig(
        name="memory",
        server_type=MCPServerType.MEMORY,
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
    )


def create_fetch_server() -> MCPServerConfig:
    """
    Create web fetch MCP server for research.
    
    Provides: fetch_url, fetch_html, extract_text
    
    Returns:
        MCP server configuration
    """
    return MCPServerConfig(
        name="fetch",
        server_type=MCPServerType.FETCH,
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-fetch"],
    )


# ============================================================================
# SDLC Phase to MCP Server Mapping
# ============================================================================

class SDLCMCPConfig(BaseModel):
    """Configuration mapping SDLC phases to MCP servers."""
    
    workspace_path: str = Field(description="Project workspace path")
    github_token: str | None = Field(default=None, description="GitHub token")
    db_connection: str | None = Field(default=None, description="Database connection string")
    
    def get_requirements_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Requirements Agent."""
        return {
            "fetch": create_fetch_server().to_dict(),
            "memory": create_memory_server().to_dict(),
        }
    
    def get_design_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Design Agent."""
        servers = {
            "fetch": create_fetch_server().to_dict(),
            "memory": create_memory_server().to_dict(),
        }
        if self.db_connection:
            servers["database"] = create_database_server(
                connection_string=self.db_connection
            ).to_dict()
        return servers
    
    def get_architecture_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Architecture Agent."""
        servers = {
            "filesystem": create_filesystem_server(self.workspace_path).to_dict(),
            "fetch": create_fetch_server().to_dict(),
        }
        if self.github_token:
            servers["github"] = create_github_server(token=self.github_token).to_dict()
        return servers
    
    def get_coding_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Coding Agent."""
        servers = {
            "filesystem": create_filesystem_server(self.workspace_path).to_dict(),
            "git": create_git_server(self.workspace_path).to_dict(),
        }
        if self.github_token:
            servers["github"] = create_github_server(token=self.github_token).to_dict()
        return servers
    
    def get_testing_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Testing Agent."""
        return {
            "filesystem": create_filesystem_server(self.workspace_path).to_dict(),
            "shell": create_shell_server(self.workspace_path).to_dict(),
            "browser": create_browser_server().to_dict(),
        }
    
    def get_cicd_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for CI/CD Agent."""
        servers = {
            "filesystem": create_filesystem_server(self.workspace_path).to_dict(),
            "git": create_git_server(self.workspace_path).to_dict(),
        }
        if self.github_token:
            servers["github"] = create_github_server(token=self.github_token).to_dict()
        return servers
    
    def get_deployment_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Deployment Agent."""
        return {
            "filesystem": create_filesystem_server(self.workspace_path).to_dict(),
            "docker": create_docker_server().to_dict(),
            "kubernetes": create_kubernetes_server().to_dict(),
        }
    
    def get_monitoring_servers(self) -> dict[str, dict[str, Any]]:
        """MCP servers for Monitoring Agent."""
        return {
            "filesystem": create_filesystem_server(self.workspace_path).to_dict(),
            "shell": create_shell_server().to_dict(),
        }
