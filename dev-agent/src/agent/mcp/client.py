"""MCP Client Implementation.

This module provides the MCP client for connecting to MCP servers,
supporting both stdio and Streamable HTTP transports.
"""

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field


class MCPTransport(str, Enum):
    """MCP transport types."""
    
    STDIO = "stdio"               # Local/sidecar servers (lowest latency)
    STREAMABLE_HTTP = "streamable_http"  # Remote/shared servers (production)
    SSE = "sse"                   # Deprecated, use streamable_http


@dataclass
class MCPServerConnection:
    """Configuration for connecting to an MCP server."""
    
    name: str
    transport: MCPTransport = MCPTransport.STDIO
    
    # stdio transport options
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    
    # HTTP transport options
    url: str | None = None
    headers: dict[str, str] | None = None
    
    # Connection state
    _connected: bool = False
    _client: Any = None


class MCPTool(BaseModel):
    """Representation of an MCP tool."""
    
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    input_schema: dict[str, Any] = Field(description="JSON Schema for input")
    server_name: str = Field(description="Source MCP server")


class MCPClient:
    """
    Client for connecting to a single MCP server.
    
    Supports stdio and HTTP transports as defined in MCP spec 2025-11-25.
    """
    
    def __init__(self, connection: MCPServerConnection):
        """
        Initialize MCP client.
        
        Args:
            connection: Server connection configuration
        """
        self.connection = connection
        self._tools: list[MCPTool] = []
        self._process: asyncio.subprocess.Process | None = None
        
    async def connect(self) -> None:
        """Establish connection to MCP server."""
        if self.connection.transport == MCPTransport.STDIO:
            await self._connect_stdio()
        elif self.connection.transport == MCPTransport.STREAMABLE_HTTP:
            await self._connect_http()
        else:
            raise ValueError(f"Unsupported transport: {self.connection.transport}")
        
        self.connection._connected = True
        
        # Fetch available tools
        await self._list_tools()
        
    async def _connect_stdio(self) -> None:
        """Connect via stdio transport."""
        if not self.connection.command:
            raise ValueError("command required for stdio transport")
            
        env = self.connection.env or {}
        
        self._process = await asyncio.create_subprocess_exec(
            self.connection.command,
            *(self.connection.args or []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        
    async def _connect_http(self) -> None:
        """Connect via Streamable HTTP transport."""
        if not self.connection.url:
            raise ValueError("url required for HTTP transport")
            
        # Initialize HTTP client
        try:
            import httpx
            self._http_client = httpx.AsyncClient(
                base_url=self.connection.url,
                headers=self.connection.headers or {},
                timeout=60.0,
            )
        except ImportError:
            raise ImportError("httpx required for HTTP transport. Install with: pip install httpx")
    
    async def _list_tools(self) -> list[MCPTool]:
        """Fetch available tools from MCP server."""
        response = await self._send_request("tools/list", {})
        
        self._tools = [
            MCPTool(
                name=tool["name"],
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
                server_name=self.connection.name,
            )
            for tool in response.get("tools", [])
        ]
        
        return self._tools
    
    @property
    def tools(self) -> list[MCPTool]:
        """Get available tools."""
        return self._tools
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        return await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
    
    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send JSON-RPC 2.0 request to MCP server.
        
        Args:
            method: RPC method name
            params: Method parameters
            
        Returns:
            Response result
        """
        request = {
            "jsonrpc": "2.0",
            "id": str(asyncio.get_event_loop().time()),
            "method": method,
            "params": params,
        }
        
        if self.connection.transport == MCPTransport.STDIO:
            return await self._send_stdio_request(request)
        else:
            return await self._send_http_request(request)
    
    async def _send_stdio_request(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Send request via stdio transport."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("Not connected via stdio")
            
        # Send request
        request_bytes = (json.dumps(request) + "\n").encode()
        self._process.stdin.write(request_bytes)
        await self._process.stdin.drain()
        
        # Read response
        response_line = await self._process.stdout.readline()
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise MCPError(
                code=response["error"].get("code", -1),
                message=response["error"].get("message", "Unknown error"),
            )
        
        return response.get("result", {})
    
    async def _send_http_request(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Send request via HTTP transport."""
        if not hasattr(self, "_http_client"):
            raise RuntimeError("Not connected via HTTP")
            
        response = await self._http_client.post(
            "/mcp",
            json=request,
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            raise MCPError(
                code=data["error"].get("code", -1),
                message=data["error"].get("message", "Unknown error"),
            )
        
        return data.get("result", {})
    
    async def disconnect(self) -> None:
        """Close connection to MCP server."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None
        
        if hasattr(self, "_http_client"):
            await self._http_client.aclose()
        
        self.connection._connected = False


class MCPError(Exception):
    """MCP protocol error."""
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"MCP Error {code}: {message}")


class MultiServerMCPClient:
    """
    Client for connecting to multiple MCP servers simultaneously.
    
    Aggregates tools from all connected servers into a unified interface.
    This is the recommended client for SDLC agents that need access to
    multiple tool types (filesystem, git, database, etc.).
    """
    
    def __init__(self, servers: dict[str, dict[str, Any]]):
        """
        Initialize multi-server client.
        
        Args:
            servers: Dictionary mapping server names to connection configs.
            
            Example:
            {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
                    "transport": "stdio",
                },
                "github": {
                    "url": "http://github-mcp:8001/mcp",
                    "transport": "streamable_http",
                },
            }
        """
        self._server_configs = servers
        self._clients: dict[str, MCPClient] = {}
        self._all_tools: list[MCPTool] = []
        
    async def connect_all(self) -> None:
        """Connect to all configured servers."""
        for name, config in self._server_configs.items():
            connection = MCPServerConnection(
                name=name,
                transport=MCPTransport(config.get("transport", "stdio")),
                command=config.get("command"),
                args=config.get("args"),
                env=config.get("env"),
                url=config.get("url"),
                headers=config.get("headers"),
            )
            
            client = MCPClient(connection)
            await client.connect()
            
            self._clients[name] = client
            self._all_tools.extend(client.tools)
    
    async def get_tools(self) -> list[MCPTool]:
        """Get all tools from all connected servers."""
        if not self._clients:
            await self.connect_all()
        return self._all_tools
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call a tool from any connected server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Find which server has this tool
        for tool in self._all_tools:
            if tool.name == tool_name:
                client = self._clients.get(tool.server_name)
                if client:
                    return await client.call_tool(tool_name, arguments)
        
        raise ValueError(f"Tool not found: {tool_name}")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()
        self._all_tools.clear()
    
    def get_server_client(self, server_name: str) -> MCPClient | None:
        """Get client for a specific server."""
        return self._clients.get(server_name)
    
    @property
    def connected_servers(self) -> list[str]:
        """List of connected server names."""
        return list(self._clients.keys())
