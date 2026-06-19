"""MCP to LangChain Tool Conversion.

This module provides utilities for converting MCP tools to LangChain-compatible
tools that can be used with LangGraph agents.

Key features:
- MCPToolWrapper: Wraps MCP tool as LangChain BaseTool
- convert_mcp_tools_to_langchain: Batch conversion utility
- MCPToolkit: Higher-level abstraction for tool management
"""

import asyncio
import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from .client import MCPClient, MCPTool, MultiServerMCPClient


def _json_schema_to_pydantic_field(
    name: str,
    schema: dict[str, Any],
    required: bool = True,
) -> tuple[type, Any]:
    """Convert JSON Schema property to Pydantic field definition."""
    json_type = schema.get("type", "string")
    description = schema.get("description", "")
    default = ... if required else None
    
    # Map JSON Schema types to Python types
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    
    python_type = type_mapping.get(json_type, str)
    
    # Handle optional fields
    if not required:
        python_type = python_type | None
    
    return (python_type, Field(default=default, description=description))


def _create_input_schema(mcp_tool: MCPTool) -> type[BaseModel]:
    """Create a Pydantic model from MCP tool input schema."""
    properties = mcp_tool.input_schema.get("properties", {})
    required = set(mcp_tool.input_schema.get("required", []))
    
    fields = {}
    for name, prop_schema in properties.items():
        fields[name] = _json_schema_to_pydantic_field(
            name, prop_schema, name in required
        )
    
    # Create dynamic Pydantic model
    model_name = f"{mcp_tool.name.title().replace('_', '')}Input"
    return create_model(model_name, **fields)


class MCPToolWrapper(BaseTool):
    """
    Wrapper that converts an MCP tool to a LangChain tool.
    
    This wrapper:
    1. Translates JSON Schema to Pydantic model for structured input
    2. Handles async/sync execution transparently
    3. Manages error handling and response formatting
    """
    
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    
    mcp_tool: MCPTool = Field(exclude=True)
    client: MCPClient = Field(exclude=True)
    args_schema: type[BaseModel] | None = Field(default=None)
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, mcp_tool: MCPTool, client: MCPClient, **kwargs):
        # Create args schema from MCP tool
        args_schema = _create_input_schema(mcp_tool)
        
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
            mcp_tool=mcp_tool,
            client=client,
            args_schema=args_schema,
            **kwargs,
        )
    
    def _run(self, **kwargs) -> str:
        """Synchronous execution - wraps async call."""
        return asyncio.run(self._arun(**kwargs))
    
    async def _arun(self, **kwargs) -> str:
        """Asynchronous execution of MCP tool."""
        try:
            result = await self.client.call_tool(self.mcp_tool.name, kwargs)
            
            # Format result based on content type
            if isinstance(result, dict):
                content = result.get("content", [])
                if content and isinstance(content, list):
                    # Extract text content from MCP response
                    texts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(item.get("text", ""))
                        elif isinstance(item, str):
                            texts.append(item)
                    return "\n".join(texts) if texts else json.dumps(result)
                return json.dumps(result)
            return str(result)
        except Exception as e:
            return f"Error executing MCP tool {self.name}: {str(e)}"


async def convert_mcp_tools_to_langchain(
    client: MCPClient | MultiServerMCPClient,
    filter_tools: list[str] | None = None,
) -> list[BaseTool]:
    """
    Convert MCP tools from a client to LangChain tools.
    
    Args:
        client: MCP client (single or multi-server)
        filter_tools: Optional list of tool names to include (None = all)
        
    Returns:
        List of LangChain-compatible tools
    """
    tools = []
    
    if isinstance(client, MultiServerMCPClient):
        # Handle multi-server client
        for server_name, single_client in client._clients.items():
            mcp_tools = await single_client.list_tools()
            for mcp_tool in mcp_tools:
                if filter_tools is None or mcp_tool.name in filter_tools:
                    # Prefix tool name with server name for disambiguation
                    prefixed_tool = MCPTool(
                        name=f"{server_name}_{mcp_tool.name}",
                        description=f"[{server_name}] {mcp_tool.description}",
                        input_schema=mcp_tool.input_schema,
                    )
                    tools.append(MCPToolWrapper(prefixed_tool, single_client))
    else:
        # Handle single client
        mcp_tools = await client.list_tools()
        for mcp_tool in mcp_tools:
            if filter_tools is None or mcp_tool.name in filter_tools:
                tools.append(MCPToolWrapper(mcp_tool, client))
    
    return tools


class MCPToolkit:
    """
    Higher-level abstraction for managing MCP tools.
    
    Provides:
    - Lazy tool loading
    - Tool categorization by SDLC phase
    - Tool caching for performance
    - Default tool configurations
    
    Usage:
        toolkit = await MCPToolkit.create(sdlc_config)
        coding_tools = await toolkit.get_tools_for_phase("coding")
    """
    
    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tools_cache: dict[str, list[BaseTool]] = {}
    
    @classmethod
    async def create(cls, config: dict[str, Any]) -> "MCPToolkit":
        """Factory method to create and initialize toolkit."""
        toolkit = cls()
        await toolkit._initialize_clients(config)
        return toolkit
    
    async def _initialize_clients(self, config: dict[str, Any]) -> None:
        """Initialize MCP clients from configuration."""
        from .servers import SDLCMCPConfig
        
        sdlc_config = SDLCMCPConfig(**config)
        
        # Map phases to server configurations
        self._phase_servers = {
            "requirements": sdlc_config.get_requirements_servers(),
            "design": sdlc_config.get_design_servers(),
            "architecture": sdlc_config.get_architecture_servers(),
            "coding": sdlc_config.get_coding_servers(),
            "testing": sdlc_config.get_testing_servers(),
            "cicd": sdlc_config.get_cicd_servers(),
            "deployment": sdlc_config.get_deployment_servers(),
            "monitoring": sdlc_config.get_monitoring_servers(),
        }
    
    async def get_tools_for_phase(
        self,
        phase: str,
        filter_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """
        Get LangChain tools for a specific SDLC phase.
        
        Args:
            phase: SDLC phase name (requirements, design, coding, etc.)
            filter_tools: Optional list of specific tools to include
            
        Returns:
            List of LangChain tools for the phase
        """
        cache_key = f"{phase}_{','.join(filter_tools or [])}"
        
        if cache_key in self._tools_cache:
            return self._tools_cache[cache_key]
        
        if phase not in self._phase_servers:
            raise ValueError(f"Unknown SDLC phase: {phase}")
        
        server_configs = self._phase_servers[phase]
        
        # Create multi-server client for this phase
        multi_client = MultiServerMCPClient(server_configs)
        await multi_client.connect()
        
        # Convert to LangChain tools
        tools = await convert_mcp_tools_to_langchain(multi_client, filter_tools)
        
        # Cache tools
        self._tools_cache[cache_key] = tools
        self._clients[phase] = multi_client
        
        return tools
    
    async def close(self) -> None:
        """Close all MCP clients."""
        for client in self._clients.values():
            if hasattr(client, "disconnect"):
                await client.disconnect()
        self._clients.clear()
        self._tools_cache.clear()


# ============================================================================
# Utility Functions for Tool Selection
# ============================================================================

def filter_tools_by_capability(
    tools: list[BaseTool],
    capabilities: list[str],
) -> list[BaseTool]:
    """
    Filter tools based on required capabilities.
    
    Args:
        tools: List of LangChain tools
        capabilities: Required capabilities (e.g., ["read", "write", "execute"])
        
    Returns:
        Filtered list of tools
    """
    capability_keywords = {
        "read": ["read", "get", "list", "fetch", "query", "describe"],
        "write": ["write", "create", "update", "set", "put", "post"],
        "delete": ["delete", "remove", "drop"],
        "execute": ["execute", "run", "eval", "call"],
        "navigate": ["navigate", "click", "type", "screenshot"],
    }
    
    keywords = set()
    for cap in capabilities:
        keywords.update(capability_keywords.get(cap, [cap]))
    
    return [
        tool for tool in tools
        if any(kw in tool.name.lower() for kw in keywords)
    ]


def get_tool_by_name(tools: list[BaseTool], name: str) -> BaseTool | None:
    """Get a specific tool by name."""
    for tool in tools:
        if tool.name == name:
            return tool
    return None


# ============================================================================
# Tool Bindings for LangGraph Agents
# ============================================================================

def create_tool_node(tools: list[BaseTool]):
    """
    Create a LangGraph ToolNode from tools.
    
    This integrates with LangGraph's prebuilt ToolNode for
    automatic tool execution in agent workflows.
    """
    from langgraph.prebuilt import ToolNode
    
    return ToolNode(tools)


def bind_tools_to_model(model, tools: list[BaseTool]):
    """
    Bind tools to a chat model for function calling.
    
    Args:
        model: LangChain chat model (e.g., ChatOpenAI, ChatAnthropic)
        tools: List of tools to bind
        
    Returns:
        Model with tools bound
    """
    return model.bind_tools(tools)
