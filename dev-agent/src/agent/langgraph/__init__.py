"""LangGraph-based orchestration for SDLC workflows.

This module provides the core LangGraph v1.0 orchestration foundation:
- Hierarchical supervisor pattern for SDLC phases
- Swarm-style handoffs for code-test-fix loops
- State management with PostgreSQL checkpointing
- Human-in-the-loop approval gates
"""

from agent.langgraph.state import SDLCState, SDLCPhase, ApprovalStatus
from agent.langgraph.graph import SDLCWorkflowGraph
from agent.langgraph.supervisor import SDLCSupervisor, create_phase_supervisor
from agent.langgraph.checkpointer import PostgresCheckpointer, CheckpointConfig

__all__ = [
    "SDLCState",
    "SDLCPhase",
    "ApprovalStatus",
    "SDLCWorkflowGraph",
    "SDLCSupervisor",
    "create_phase_supervisor",
    "PostgresCheckpointer",
    "CheckpointConfig",
]
