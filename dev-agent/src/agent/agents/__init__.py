"""SDLC Specialized Agents - Phase 4."""

from agent.agents.architecture_agent import ArchitectureAgent, create_architecture_agent
from agent.agents.base import (
    AgentCapability,
    AgentConfig,
    AgentRole,
    AgentTask,
    BaseAgent,
    TaskStatus,
    create_agent_config,
)
from agent.agents.deployment_agent import DeploymentAgent, create_deployment_agent
from agent.agents.implementation_agent import ImplementationAgent, create_implementation_agent
from agent.agents.operations_agent import OperationsAgent, create_operations_agent
from agent.agents.requirements_agent import RequirementsAgent, create_requirements_agent
from agent.agents.testing_agent import TestingAgent, create_testing_agent

__all__ = [
    # Base classes and types
    "BaseAgent",
    "AgentRole",
    "AgentTask",
    "AgentConfig",
    "AgentCapability",
    "TaskStatus",
    "create_agent_config",
    # Specialized agents
    "RequirementsAgent",
    "ArchitectureAgent",
    "ImplementationAgent",
    "TestingAgent",
    "DeploymentAgent",
    "OperationsAgent",
    # Factory functions
    "create_requirements_agent",
    "create_architecture_agent",
    "create_implementation_agent",
    "create_testing_agent",
    "create_deployment_agent",
    "create_operations_agent",
]
