"""MCP-Enhanced SDLC Agent Base.

Provides base class for agents with MCP tool integration and LangGraph compatibility.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from agent.langgraph.state import SDLCPhase, SDLCState
from agent.mcp.client import MCPClient, MultiServerMCPClient
from agent.mcp.servers import MCPServerConfig, SDLCMCPConfig
from agent.mcp.tools import MCPToolkit, bind_tools_to_model, convert_mcp_tools_to_langchain


class AgentOutput(BaseModel):
    """Structured output from agent execution."""
    
    phase: SDLCPhase = Field(description="SDLC phase")
    status: Literal["success", "failed", "needs_input"] = Field(description="Execution status")
    deliverables: dict[str, Any] = Field(default={}, description="Phase deliverables")
    messages: list[dict[str, str]] = Field(default=[], description="Agent messages")
    artifacts: list[str] = Field(default=[], description="Generated artifact IDs")
    next_actions: list[str] = Field(default=[], description="Recommended next steps")
    requires_approval: bool = Field(default=False, description="Needs human approval")
    error: str | None = Field(default=None, description="Error if failed")


class MCPAgentBase(ABC):
    """
    Base class for MCP-enhanced SDLC agents.
    
    Integrates with:
    - MCP servers for phase-specific tools
    - LangGraph for state management
    - LLMs for reasoning
    
    Each specialized agent:
    - Has a dedicated MCP tool set
    - Works within LangGraph workflow
    - Produces structured deliverables
    """
    
    # Override in subclasses
    PHASE: SDLCPhase
    
    def __init__(
        self,
        model: Any,  # ChatOpenAI, ChatAnthropic, etc.
        mcp_config: SDLCMCPConfig | None = None,
        max_iterations: int = 25,
    ):
        """
        Initialize MCP-enhanced agent.
        
        Args:
            model: LangChain chat model
            mcp_config: MCP server configuration
            max_iterations: Max reasoning iterations
        """
        self.model = model
        self.mcp_config = mcp_config or SDLCMCPConfig()
        self.max_iterations = max_iterations
        
        self._mcp_client: MultiServerMCPClient | None = None
        self._toolkit: MCPToolkit | None = None
        self._tools: list[BaseTool] = []
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt defining agent behavior."""
        pass
    
    @property
    @abstractmethod
    def role_description(self) -> str:
        """Human-readable role description."""
        pass
    
    @property
    def phase_servers(self) -> list[MCPServerConfig]:
        """Get MCP servers for this agent's phase."""
        return self.mcp_config.get_servers_for_phase(self.PHASE.value)
    
    async def initialize(self) -> None:
        """Initialize MCP connections and tools."""
        if self._mcp_client is not None:
            return
        
        # Create MCP client
        server_configs = {s.name: s for s in self.phase_servers}
        self._mcp_client = MultiServerMCPClient(server_configs)
        await self._mcp_client.connect_all()
        
        # Create toolkit
        self._toolkit = MCPToolkit(self._mcp_client)
        
        # Get LangChain tools
        self._tools = await self._toolkit.get_tools()
    
    async def shutdown(self) -> None:
        """Clean up MCP connections."""
        if self._mcp_client:
            await self._mcp_client.disconnect_all()
            self._mcp_client = None
            self._toolkit = None
            self._tools = []
    
    async def __aenter__(self) -> "MCPAgentBase":
        await self.initialize()
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.shutdown()
    
    def get_tools(self) -> list[BaseTool]:
        """Get available tools for this agent."""
        return self._tools
    
    def get_bound_model(self) -> Any:
        """Get model with tools bound."""
        return bind_tools_to_model(self.model, self._tools)
    
    @abstractmethod
    async def process(self, state: SDLCState) -> AgentOutput:
        """
        Process current state and produce output.
        
        Args:
            state: Current SDLC workflow state
            
        Returns:
            AgentOutput with deliverables
        """
        pass
    
    async def invoke(self, state: SDLCState) -> dict[str, Any]:
        """
        Invoke agent as LangGraph node.
        
        Args:
            state: Current state
            
        Returns:
            State updates
        """
        await self.initialize()
        
        try:
            output = await self.process(state)
            
            return {
                "phase_outputs": {self.PHASE.value: output.deliverables},
                "messages": [
                    {"role": "assistant", "content": m.get("content", "")}
                    for m in output.messages
                ],
                "current_phase": (
                    self._get_next_phase() if output.status == "success" 
                    else state["current_phase"]
                ),
                "approval_required": output.requires_approval,
            }
        except Exception as e:
            return {
                "messages": [{"role": "assistant", "content": f"Error in {self.PHASE.value}: {e}"}],
                "error": str(e),
            }
    
    def _get_next_phase(self) -> SDLCPhase:
        """Get next phase in workflow."""
        phase_order = [
            SDLCPhase.REQUIREMENTS,
            SDLCPhase.DESIGN,
            SDLCPhase.ARCHITECTURE,
            SDLCPhase.CODING,
            SDLCPhase.TESTING,
            SDLCPhase.CICD,
            SDLCPhase.DEPLOYMENT,
            SDLCPhase.MONITORING,
        ]
        
        try:
            idx = phase_order.index(self.PHASE)
            if idx < len(phase_order) - 1:
                return phase_order[idx + 1]
        except ValueError:
            pass
        
        return self.PHASE
    
    def _build_messages(
        self,
        state: SDLCState,
        task_prompt: str,
    ) -> list[BaseMessage]:
        """Build message list for LLM."""
        messages: list[BaseMessage] = [
            SystemMessage(content=self.system_prompt),
        ]
        
        # Add context from previous phases
        if state.get("phase_outputs"):
            context_parts = ["## Previous Phase Outputs"]
            for phase, output in state["phase_outputs"].items():
                context_parts.append(f"\n### {phase}")
                context_parts.append(str(output)[:2000])  # Truncate large outputs
            
            messages.append(HumanMessage(content="\n".join(context_parts)))
        
        # Add current task
        messages.append(HumanMessage(content=task_prompt))
        
        return messages
    
    async def _execute_with_tools(
        self,
        messages: list[BaseMessage],
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Execute agent reasoning with tool use.
        
        Returns:
            Tuple of (final_response, tool_call_log)
        """
        tool_log = []
        bound_model = self.get_bound_model()
        
        current_messages = list(messages)
        
        for iteration in range(self.max_iterations):
            response = await bound_model.ainvoke(current_messages)
            current_messages.append(response)
            
            # Check for tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    # Execute tool
                    tool = next(
                        (t for t in self._tools if t.name == tool_name),
                        None
                    )
                    
                    if tool:
                        try:
                            result = await tool.ainvoke(tool_args)
                            tool_result = str(result)
                        except Exception as e:
                            tool_result = f"Error: {e}"
                    else:
                        tool_result = f"Unknown tool: {tool_name}"
                    
                    tool_log.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": tool_result[:1000],  # Truncate
                    })
                    
                    # Add tool result to messages
                    from langchain_core.messages import ToolMessage
                    current_messages.append(
                        ToolMessage(
                            content=tool_result,
                            tool_call_id=tool_call.get("id", ""),
                        )
                    )
            else:
                # No tool calls - final response
                return response.content, tool_log
        
        # Max iterations reached
        return current_messages[-1].content, tool_log
