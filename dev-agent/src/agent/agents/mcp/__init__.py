"""MCP-Enhanced SDLC Agents Module.

Provides specialized agents for each SDLC phase with MCP tool integration.
"""

from .base import AgentOutput, MCPAgentBase
from .requirements import RequirementsAgent
from .design import DesignAgent
from .architecture import ArchitectureAgent
from .coding import CodingAgent
from .testing import TestingAgent
from .cicd import CICDAgent
from .deployment import DeploymentAgent
from .monitoring import MonitoringAgent

__all__ = [
    # Base
    "AgentOutput",
    "MCPAgentBase",
    # Specialized Agents
    "RequirementsAgent",
    "DesignAgent",
    "ArchitectureAgent",
    "CodingAgent",
    "TestingAgent",
    "CICDAgent",
    "DeploymentAgent",
    "MonitoringAgent",
]
