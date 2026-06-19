"""A2A (Agent-to-Agent) Protocol Integration Module.

This module implements Google's A2A protocol (v1.0 RC) for inter-agent
communication, enabling SDLC agents to interact with each other through
standardized JSON-RPC 2.0 endpoints.

Protocol Reference: https://google.github.io/A2A/v1.0-rc
SDK: a2a-sdk v0.3.22

Key Components:
- agent_card: Agent capability advertisement via .well-known/agent.json
- server: HTTP server wrapper exposing LangGraph agents via A2A
- client: A2A client for agent-to-agent communication
- task: Task lifecycle management (submitted → working → input-required → completed)
"""

from agent.a2a.agent_card import (
    A2ACapability,
    AgentCard,
    AgentIdentity,
    AgentSkill,
    create_agent_card,
)
from agent.a2a.client import A2AClient, A2AAgentRegistry, A2AResponse
from agent.a2a.server import A2AServer, create_a2a_server, expose_langgraph_agent
from agent.a2a.task import TaskManager, TaskState, TaskStatus

__all__ = [
    # Agent Card
    "AgentCard",
    "AgentIdentity",
    "AgentSkill",
    "A2ACapability",
    "create_agent_card",
    # Server
    "A2AServer",
    "create_a2a_server",
    "expose_langgraph_agent",
    # Client
    "A2AClient",
    "A2AAgentRegistry",
    "A2AResponse",
    # Task
    "TaskManager",
    "TaskState",
    "TaskStatus",
]
