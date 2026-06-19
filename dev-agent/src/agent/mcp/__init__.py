"""MCP (Model Context Protocol) Integration Module.

This module provides the universal tool layer for SDLC agents using MCP,
standardizing how agents connect to filesystem, git, databases, browsers,
and other external tools via JSON-RPC 2.0.

Components:
- client: Low-level MCP client implementations (MCPClient, MultiServerMCPClient)
- servers: MCP server configurations for SDLC phases
- tools: MCP to LangChain tool conversion utilities
"""

from agent.mcp.client import MCPClient, MCPError, MCPTool, MCPTransport, MultiServerMCPClient
from agent.mcp.servers import (
    MCPServerConfig,
    MCPServerType,
    SDLCMCPConfig,
    create_browser_server,
    create_database_server,
    create_docker_server,
    create_fetch_server,
    create_filesystem_server,
    create_git_server,
    create_github_server,
    create_github_server_http,
    create_kubernetes_server,
    create_memory_server,
    create_shell_server,
)
from agent.mcp.tools import (
    MCPToolkit,
    MCPToolWrapper,
    bind_tools_to_model,
    convert_mcp_tools_to_langchain,
    create_tool_node,
    filter_tools_by_capability,
    get_tool_by_name,
)

__all__ = [
    # Client
    "MCPClient",
    "MultiServerMCPClient",
    "MCPTool",
    "MCPTransport",
    "MCPError",
    # Server configs
    "MCPServerConfig",
    "MCPServerType",
    "SDLCMCPConfig",
    "create_filesystem_server",
    "create_git_server",
    "create_github_server",
    "create_github_server_http",
    "create_database_server",
    "create_browser_server",
    "create_docker_server",
    "create_kubernetes_server",
    "create_shell_server",
    "create_memory_server",
    "create_fetch_server",
    # Tools
    "MCPToolkit",
    "MCPToolWrapper",
    "convert_mcp_tools_to_langchain",
    "create_tool_node",
    "bind_tools_to_model",
    "filter_tools_by_capability",
    "get_tool_by_name",
]
