# LangGraph Orchestration Implementation Guide

> **Version**: 1.0.0  
> **Target**: LangGraph v1.0.7  
> **Last Updated**: 2026-02-06  
> **Companion Document**: [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [State Management](#2-state-management)
3. [Supervisor Pattern Implementation](#3-supervisor-pattern-implementation)
4. [Hierarchical Supervisor Design](#4-hierarchical-supervisor-design)
5. [Swarm Pattern for Code-Test Loop](#5-swarm-pattern-for-code-test-loop)
6. [Checkpointing and Persistence](#6-checkpointing-and-persistence)
7. [Human-in-the-Loop Gates](#7-human-in-the-loop-gates)
8. [Parallel Execution](#8-parallel-execution)
9. [Error Handling and Retry](#9-error-handling-and-retry)
10. [Complete SDLC Graph Definition](#10-complete-sdlc-graph-definition)
11. [Testing LangGraph Workflows](#11-testing-langgraph-workflows)

---

## 1. Introduction

### 1.1 LangGraph v1.0.7 Overview

LangGraph is a low-level orchestration framework for building, managing, and deploying long-running, stateful agents. It provides:

- **Durable execution** through checkpoint-based state persistence
- **Human-in-the-loop capabilities** via dynamic interrupts
- **Multi-agent coordination** through supervisor and swarm patterns
- **Streaming support** for real-time execution feedback
- **Memory management** for context retention across interactions

```mermaid
graph TB
    subgraph LangGraph Core
        SG[StateGraph]
        N[Nodes]
        E[Edges]
        CP[Checkpointer]
    end
    
    subgraph State Management
        TD[TypedDict Schema]
        R[Reducers]
        CH[Channels]
    end
    
    subgraph Execution
        INV[Invoke]
        STR[Stream]
        INT[Interrupt]
    end
    
    SG --> N & E
    SG --> CP
    TD --> SG
    R --> TD
    CP --> INV & STR & INT
```

### 1.2 Why LangGraph for SDLC Automation

The Software Development Lifecycle requires orchestration patterns that LangGraph excels at:

| SDLC Requirement | LangGraph Solution |
|-----------------|-------------------|
| **Long-running tasks** | Durable checkpoints survive process restarts |
| **Human approvals** | `interrupt()` pauses for review gates |
| **Multi-agent coordination** | Supervisor and swarm patterns |
| **Parallel work** | `Send` API for fan-out execution |
| **Error recovery** | Checkpoint-based retry from failure point |
| **State tracking** | TypedDict-based state with reducers |

### 1.3 Key Concepts

#### StateGraph

The core building block that defines a directed graph of nodes connected by edges:

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(MyState)
graph.add_node("node_name", node_function)
graph.add_edge(START, "node_name")
graph.add_edge("node_name", END)
app = graph.compile()
```

#### Nodes

Functions that receive state and return state updates:

```python
def my_node(state: MyState) -> dict:
    # Process state
    return {"key": "updated_value"}
```

#### Edges

Connections between nodes that control execution flow:
- **Normal edges**: Direct transitions
- **Conditional edges**: Route based on state
- **Entry/Exit edges**: Connect to `START` and `END`

#### Checkpointers

Persistence backends that save state between executions:
- `MemorySaver` - In-memory (development)
- `PostgresSaver` - PostgreSQL (production)
- `SqliteSaver` - SQLite (lightweight)

---

## 2. State Management

### 2.1 Complete SDLCState TypedDict Definition

The state schema defines all data flowing through the SDLC workflow:

```python
# src/agent/langgraph/state.py

from typing import TypedDict, Annotated, Literal, Sequence, Any
from datetime import datetime
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
import operator


def add_to_list(left: list, right: list) -> list:
    """Reducer that appends items to a list."""
    return left + right


def replace_value(left: Any, right: Any) -> Any:
    """Reducer that replaces with the latest value."""
    return right


class CodeFile(TypedDict):
    """Represents a generated code file."""
    path: str
    content: str
    language: str
    imports: list[str]
    exports: list[str]
    checksum: str


class TestResult(TypedDict):
    """Represents a test execution result."""
    test_file: str
    test_name: str
    status: Literal["passed", "failed", "skipped", "error"]
    duration_ms: float
    error_message: str | None
    stack_trace: str | None


class ApprovalRequest(TypedDict):
    """Represents a pending human approval."""
    id: str
    gate: str
    phase: str
    artifact_id: str
    summary: str
    details: dict
    requested_at: str
    options: list[str]


class SDLCMessage(TypedDict):
    """Message structure for SDLC communication."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    agent_id: str | None
    timestamp: str
    metadata: dict


class SDLCState(TypedDict):
    """Main state schema for the SDLC workflow.
    
    This TypedDict defines all state channels used by the LangGraph.
    Fields annotated with reducers will aggregate updates rather than replace.
    """
    
    # === Conversation and Messages ===
    messages: Annotated[Sequence[AnyMessage], add_messages]
    """Conversation history with automatic message aggregation."""
    
    # === Project Context ===
    project_id: str
    """Unique identifier for the project."""
    
    project_name: str
    """Human-readable project name."""
    
    project_path: str
    """Filesystem path to project root."""
    
    # === Phase Tracking ===
    current_phase: Literal[
        "requirements",
        "system_design",
        "architecture",
        "implementation",
        "testing",
        "ci_cd",
        "deployment",
        "monitoring"
    ]
    """Current SDLC phase being executed."""
    
    phase_status: Literal["pending", "in_progress", "blocked", "completed", "failed"]
    """Status of the current phase."""
    
    completed_phases: Annotated[list[str], add_to_list]
    """List of successfully completed phases."""
    
    # === Artifacts ===
    artifacts: dict[str, dict]
    """Phase-keyed artifact data: {phase: artifact_data}."""
    
    code_files: Annotated[list[CodeFile], add_to_list]
    """Generated code files with reducer for aggregation."""
    
    test_results: Annotated[list[TestResult], add_to_list]
    """Test execution results with reducer for aggregation."""
    
    # === Human Approval ===
    pending_approvals: list[ApprovalRequest]
    """Queue of pending human approval requests."""
    
    approved_items: list[str]
    """IDs of approved artifacts/decisions."""
    
    rejected_items: list[str]
    """IDs of rejected artifacts with feedback."""
    
    # === Error Handling ===
    errors: Annotated[list[dict], add_to_list]
    """Accumulated errors during execution."""
    
    retry_count: int
    """Number of retry attempts for current operation."""
    
    max_retries: int
    """Maximum retries before failure."""
    
    # === Routing ===
    next_agent: str | None
    """Name of the next agent to route to."""
    
    routing_reason: str | None
    """Explanation for routing decision."""
    
    active_agent: str
    """Currently executing agent name."""
    
    # === Execution Metadata ===
    iteration: int
    """Current iteration count."""
    
    max_iterations: int
    """Maximum allowed iterations."""
    
    started_at: str
    """ISO timestamp of workflow start."""
    
    last_updated_at: str
    """ISO timestamp of last state update."""
```

### 2.2 Annotated Reducers for List Aggregation

Reducers control how state updates are applied when multiple nodes write to the same key:

```python
from typing import Annotated
import operator

class State(TypedDict):
    # Using built-in add_messages for conversation history
    messages: Annotated[list[AnyMessage], add_messages]
    
    # Using operator.add for simple list concatenation
    errors: Annotated[list[dict], operator.add]
    
    # Custom reducer for deduplication
    code_files: Annotated[list[CodeFile], dedupe_code_files]


def dedupe_code_files(existing: list[CodeFile], new: list[CodeFile]) -> list[CodeFile]:
    """Reducer that deduplicates code files by path."""
    path_to_file = {f["path"]: f for f in existing}
    for file in new:
        path_to_file[file["path"]] = file  # Update or add
    return list(path_to_file.values())
```

### 2.3 State Channels and Message Passing

State channels enable typed communication between nodes:

```python
from langgraph.graph import StateGraph

# Define state with channels
class WorkerState(TypedDict):
    """State for individual worker nodes."""
    task: dict
    result: str
    worker_id: str


def orchestrator(state: SDLCState) -> dict:
    """Orchestrator delegates to workers via state updates."""
    return {
        "next_agent": "coding_agent",
        "routing_reason": "Implementation phase requires coding"
    }


def coding_worker(state: SDLCState) -> dict:
    """Worker processes task and returns results."""
    new_file = CodeFile(
        path="src/main.py",
        content="# Generated code",
        language="python",
        imports=[],
        exports=["main"],
        checksum="abc123"
    )
    return {
        "code_files": [new_file],  # Reducer appends to list
        "phase_status": "in_progress"
    }
```

---

## 3. Supervisor Pattern Implementation

### 3.1 Using langgraph-supervisor Package

The supervisor pattern uses a central orchestrator to route tasks to specialized workers:

```python
# src/agent/langgraph/supervisor.py

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from agent.langgraph.state import SDLCState


class RoutingDecision(BaseModel):
    """Schema for supervisor routing decisions."""
    next_agent: Literal[
        "requirements_agent",
        "system_design_agent",
        "architecture_agent",
        "coding_agent",
        "testing_agent",
        "cicd_agent",
        "deployment_agent",
        "monitoring_agent",
        "human_approval",
        "complete"
    ] = Field(description="The next agent to route to")
    reason: str = Field(description="Explanation for the routing decision")


def create_supervisor(llm: ChatOpenAI) -> StateGraph:
    """Create the master supervisor node."""
    
    # Augment LLM with structured output for routing
    router = llm.with_structured_output(RoutingDecision)
    
    def supervisor_node(state: SDLCState) -> dict:
        """Supervisor decides which agent handles the next step."""
        
        # Check for pending approvals first
        if state.get("pending_approvals"):
            return {
                "next_agent": "human_approval",
                "routing_reason": "Human approval required"
            }
        
        # Check for completion
        if state.get("phase_status") == "completed":
            phase = state.get("current_phase")
            phases = [
                "requirements", "system_design", "architecture",
                "implementation", "testing", "ci_cd",
                "deployment", "monitoring"
            ]
            current_idx = phases.index(phase)
            
            if current_idx >= len(phases) - 1:
                return {
                    "next_agent": "complete",
                    "routing_reason": "All SDLC phases completed"
                }
            
            next_phase = phases[current_idx + 1]
            return {
                "current_phase": next_phase,
                "phase_status": "pending",
                "next_agent": f"{next_phase}_agent",
                "routing_reason": f"Advancing to {next_phase} phase"
            }
        
        # Use LLM to decide routing based on current state
        decision = router.invoke([
            SystemMessage(content="""You are an SDLC workflow supervisor.
            Analyze the current state and decide which agent should handle the next step.
            Consider the current phase, status, and any blockers."""),
            HumanMessage(content=f"""
            Current Phase: {state.get('current_phase')}
            Phase Status: {state.get('phase_status')}
            Errors: {state.get('errors', [])}
            Last Message: {state.get('messages', [])[-1] if state.get('messages') else 'None'}
            """)
        ])
        
        return {
            "next_agent": decision.next_agent,
            "routing_reason": decision.reason
        }
    
    return supervisor_node
```

### 3.2 Creating the Master Orchestrator

```python
# src/agent/langgraph/orchestrator.py

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from agent.langgraph.state import SDLCState
from agent.langgraph.supervisor import create_supervisor
from agent.langgraph.nodes import (
    requirements_node,
    system_design_node,
    architecture_node,
    coding_node,
    testing_node,
    cicd_node,
    deployment_node,
    monitoring_node,
    human_approval_node,
)


def create_sdlc_orchestrator(llm, checkpointer: PostgresSaver) -> StateGraph:
    """Create the complete SDLC orchestration graph."""
    
    # Initialize graph with state schema
    builder = StateGraph(SDLCState)
    
    # Add supervisor node
    supervisor = create_supervisor(llm)
    builder.add_node("supervisor", supervisor)
    
    # Add worker nodes
    builder.add_node("requirements_agent", requirements_node)
    builder.add_node("system_design_agent", system_design_node)
    builder.add_node("architecture_agent", architecture_node)
    builder.add_node("coding_agent", coding_node)
    builder.add_node("testing_agent", testing_node)
    builder.add_node("cicd_agent", cicd_node)
    builder.add_node("deployment_agent", deployment_node)
    builder.add_node("monitoring_agent", monitoring_node)
    builder.add_node("human_approval", human_approval_node)
    
    # Entry point
    builder.add_edge(START, "supervisor")
    
    # Conditional routing from supervisor
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "requirements_agent": "requirements_agent",
            "system_design_agent": "system_design_agent",
            "architecture_agent": "architecture_agent",
            "coding_agent": "coding_agent",
            "testing_agent": "testing_agent",
            "cicd_agent": "cicd_agent",
            "deployment_agent": "deployment_agent",
            "monitoring_agent": "monitoring_agent",
            "human_approval": "human_approval",
            "complete": END,
        }
    )
    
    # All workers return to supervisor
    for agent in [
        "requirements_agent", "system_design_agent", "architecture_agent",
        "coding_agent", "testing_agent", "cicd_agent",
        "deployment_agent", "monitoring_agent", "human_approval"
    ]:
        builder.add_edge(agent, "supervisor")
    
    # Compile with checkpointer
    return builder.compile(checkpointer=checkpointer)


def route_from_supervisor(state: SDLCState) -> str:
    """Route to the next node based on supervisor decision."""
    return state.get("next_agent", "complete")
```

### 3.3 Routing Logic and Conditional Edges

```python
from typing import Literal

def create_phase_router(state: SDLCState) -> Literal[
    "continue", "approval_needed", "error", "complete"
]:
    """Router function for phase-level decisions."""
    
    # Check for errors
    if state.get("errors") and state.get("retry_count", 0) >= state.get("max_retries", 3):
        return "error"
    
    # Check for pending approvals
    if state.get("pending_approvals"):
        return "approval_needed"
    
    # Check for completion
    if state.get("phase_status") == "completed":
        return "complete"
    
    return "continue"


# Using conditional edges with the router
builder.add_conditional_edges(
    "phase_processor",
    create_phase_router,
    {
        "continue": "worker_node",
        "approval_needed": "approval_gate",
        "error": "error_handler",
        "complete": "phase_finalizer",
    }
)
```

### 3.4 Worker Node Definitions

```python
# src/agent/langgraph/nodes/requirements.py

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agent.langgraph.state import SDLCState


REQUIREMENTS_SYSTEM_PROMPT = """You are a Requirements Analysis Agent specialized in software requirements engineering.

## Expertise
- Stakeholder analysis and requirements elicitation
- PRD (Product Requirements Document) generation
- User story creation following INVEST principles
- Acceptance criteria in Given-When-Then format
- MoSCoW prioritization

## Output Format
Always provide structured output with:
1. PRD summary
2. User stories with acceptance criteria
3. Non-functional requirements
4. Priority classification"""


async def requirements_node(state: SDLCState) -> dict:
    """Process requirements phase."""
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    # Get the task from messages
    last_message = state["messages"][-1] if state["messages"] else None
    task = last_message.content if last_message else state.get("project_name", "")
    
    # Generate requirements analysis
    response = await llm.ainvoke([
        SystemMessage(content=REQUIREMENTS_SYSTEM_PROMPT),
        HumanMessage(content=f"Analyze requirements for: {task}")
    ])
    
    # Parse and structure the output
    requirements_artifact = {
        "prd": response.content,
        "generated_at": datetime.now().isoformat(),
        "agent": "requirements_agent"
    }
    
    return {
        "messages": [AIMessage(content=response.content, name="requirements_agent")],
        "artifacts": {**state.get("artifacts", {}), "requirements": requirements_artifact},
        "phase_status": "completed",
        "pending_approvals": [{
            "id": f"req_{state['project_id']}",
            "gate": "prd_approval",
            "phase": "requirements",
            "artifact_id": "requirements",
            "summary": "PRD ready for review",
            "details": {"preview": response.content[:500]},
            "requested_at": datetime.now().isoformat(),
            "options": ["approve", "reject", "request_changes"]
        }]
    }
```

---

## 4. Hierarchical Supervisor Design

### 4.1 Three-Level Hierarchy

The SDLC workflow uses a 3-level hierarchy for scalable orchestration:

```mermaid
graph TB
    subgraph Level 0 - Master Supervisor
        MS[SDLC Master Supervisor]
    end
    
    subgraph Level 1 - Phase Supervisors
        PS_REQ[Requirements Phase Supervisor]
        PS_DEV[Development Phase Supervisor]
        PS_OPS[Operations Phase Supervisor]
    end
    
    subgraph Level 2 - Workers
        W_REQ[Requirements Agent]
        W_SYS[System Design Agent]
        W_ARCH[Architecture Agent]
        W_CODE1[Coding Agent 1]
        W_CODE2[Coding Agent 2]
        W_TEST[Testing Agent]
        W_CICD[CI/CD Agent]
        W_DEP[Deployment Agent]
        W_MON[Monitoring Agent]
    end
    
    MS --> PS_REQ
    MS --> PS_DEV
    MS --> PS_OPS
    
    PS_REQ --> W_REQ
    PS_REQ --> W_SYS
    
    PS_DEV --> W_ARCH
    PS_DEV --> W_CODE1
    PS_DEV --> W_CODE2
    PS_DEV --> W_TEST
    
    PS_OPS --> W_CICD
    PS_OPS --> W_DEP
    PS_OPS --> W_MON
```

### 4.2 Sub-graphs as Workers Pattern

```python
# src/agent/langgraph/subgraphs/development_phase.py

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import operator


class DevelopmentState(TypedDict):
    """State schema for development phase sub-graph."""
    parent_project_id: str
    architecture_spec: dict
    code_files: Annotated[list, operator.add]
    test_results: Annotated[list, operator.add]
    current_task: str
    iteration: int
    max_iterations: int


def create_development_subgraph() -> StateGraph:
    """Create the development phase sub-graph."""
    
    builder = StateGraph(DevelopmentState)
    
    # Add nodes
    builder.add_node("architect", architecture_worker)
    builder.add_node("coder", coding_worker)
    builder.add_node("tester", testing_worker)
    builder.add_node("dev_supervisor", development_supervisor)
    
    # Entry starts with supervisor
    builder.add_edge(START, "dev_supervisor")
    
    # Supervisor routes to workers
    builder.add_conditional_edges(
        "dev_supervisor",
        route_development_task,
        {
            "architect": "architect",
            "coder": "coder",
            "tester": "tester",
            "done": END,
        }
    )
    
    # Workers return to supervisor
    builder.add_edge("architect", "dev_supervisor")
    builder.add_edge("coder", "dev_supervisor")
    builder.add_edge("tester", "dev_supervisor")
    
    return builder.compile()


def development_supervisor(state: DevelopmentState) -> dict:
    """Development phase supervisor decides next task."""
    
    # Check if architecture is ready
    if not state.get("architecture_spec"):
        return {"current_task": "architect"}
    
    # Check if code is complete
    if not state.get("code_files"):
        return {"current_task": "coder"}
    
    # Check if tests passed
    test_results = state.get("test_results", [])
    failed_tests = [t for t in test_results if t["status"] == "failed"]
    
    if failed_tests and state.get("iteration", 0) < state.get("max_iterations", 5):
        return {
            "current_task": "coder",
            "iteration": state.get("iteration", 0) + 1
        }
    
    # Run tests if we have code
    if not test_results:
        return {"current_task": "tester"}
    
    return {"current_task": "done"}


def route_development_task(state: DevelopmentState) -> str:
    """Route to appropriate development worker."""
    return state.get("current_task", "done")
```

### 4.3 State Inheritance and Isolation

```python
# Parent graph integrating sub-graphs

from langgraph.graph import StateGraph, START, END

def create_master_graph():
    """Create master graph that uses sub-graphs as nodes."""
    
    builder = StateGraph(SDLCState)
    
    # Create sub-graphs
    requirements_subgraph = create_requirements_subgraph()
    development_subgraph = create_development_subgraph()
    operations_subgraph = create_operations_subgraph()
    
    # Add sub-graphs as nodes
    builder.add_node("requirements_phase", requirements_subgraph)
    builder.add_node("development_phase", development_subgraph)
    builder.add_node("operations_phase", operations_subgraph)
    builder.add_node("master_supervisor", master_supervisor_node)
    
    # Entry and routing
    builder.add_edge(START, "master_supervisor")
    
    builder.add_conditional_edges(
        "master_supervisor",
        route_to_phase,
        {
            "requirements": "requirements_phase",
            "development": "development_phase",
            "operations": "operations_phase",
            "complete": END,
        }
    )
    
    # Phases return to master supervisor
    builder.add_edge("requirements_phase", "master_supervisor")
    builder.add_edge("development_phase", "master_supervisor")
    builder.add_edge("operations_phase", "master_supervisor")
    
    return builder.compile()
```

---

## 5. Swarm Pattern for Code-Test Loop

### 5.1 Using langgraph-swarm for Peer-to-Peer Handoffs

The swarm pattern enables agents to hand off control directly to each other:

```python
# src/agent/langgraph/swarm/code_test_swarm.py

from typing import Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph_swarm import create_handoff_tool, create_swarm

from agent.langgraph.state import SDLCState


def create_code_test_swarm(llm: ChatOpenAI):
    """Create a swarm of coding and testing agents."""
    
    # Create handoff tools
    transfer_to_tester = create_handoff_tool(
        agent_name="testing_agent",
        description="Transfer to testing agent when code is ready for testing"
    )
    
    transfer_to_coder = create_handoff_tool(
        agent_name="coding_agent",
        description="Transfer to coding agent when tests fail and fixes are needed"
    )
    
    transfer_to_supervisor = create_handoff_tool(
        agent_name="supervisor",
        description="Transfer to supervisor when tests pass and phase is complete"
    )
    
    # Define coding agent tools
    @tool
    def write_code(file_path: str, content: str) -> str:
        """Write code to a file."""
        # In production, this would use MCP filesystem server
        return f"Successfully wrote {len(content)} characters to {file_path}"
    
    @tool
    def read_file(file_path: str) -> str:
        """Read content from a file."""
        # In production, this would use MCP filesystem server
        return "# File content here"
    
    # Define testing agent tools
    @tool
    def run_tests(test_pattern: str) -> str:
        """Run tests matching the pattern."""
        # In production, this would use MCP shell server
        return "All tests passed: 10/10"
    
    @tool
    def get_coverage(file_path: str) -> str:
        """Get test coverage for a file."""
        return "Coverage: 85%"
    
    # Create agents
    coding_agent = create_react_agent(
        llm,
        tools=[write_code, read_file, transfer_to_tester],
        state_schema=SDLCState,
        state_modifier="""You are a coding agent that implements features.
        When code is ready for testing, transfer to testing_agent.
        Focus on writing clean, well-documented code."""
    )
    
    testing_agent = create_react_agent(
        llm,
        tools=[run_tests, get_coverage, transfer_to_coder, transfer_to_supervisor],
        state_schema=SDLCState,
        state_modifier="""You are a testing agent that validates code.
        If tests fail, transfer back to coding_agent with failure details.
        If tests pass with good coverage, transfer to supervisor."""
    )
    
    # Create swarm
    swarm = create_swarm(
        agents=[coding_agent, testing_agent],
        default_active_agent="coding_agent"
    )
    
    return swarm.compile()
```

### 5.2 create_handoff_tool for Agent-to-Agent Transfer

```python
# Custom handoff tool with context transfer

from typing import Annotated
from langchain.tools import tool, BaseTool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState


def create_custom_handoff_tool(
    *,
    agent_name: str,
    name: str | None = None,
    description: str | None = None
) -> BaseTool:
    """Create a handoff tool that transfers context to another agent."""
    
    tool_name = name or f"transfer_to_{agent_name}"
    tool_description = description or f"Transfer control to {agent_name}"
    
    @tool(tool_name, description=tool_description)
    def handoff_to_agent(
        task_description: Annotated[
            str,
            "Detailed description of what the next agent should do"
        ],
        context_data: Annotated[
            dict,
            "Relevant context data to pass to the next agent"
        ],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Execute handoff to another agent with context."""
        
        tool_message = ToolMessage(
            content=f"Successfully transferred to {agent_name}",
            name=tool_name,
            tool_call_id=tool_call_id,
        )
        
        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={
                "messages": state["messages"] + [tool_message],
                "active_agent": agent_name,
                "task_description": task_description,
                "handoff_context": context_data,
            },
        )
    
    return handoff_to_agent


# Usage example
transfer_to_testing = create_custom_handoff_tool(
    agent_name="testing_agent",
    name="request_testing",
    description="Request testing agent to validate the implemented code"
)
```

### 5.3 Exit Conditions and Loop Prevention

```python
# src/agent/langgraph/swarm/loop_prevention.py

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt


class SwarmState(TypedDict):
    """State for code-test swarm with loop prevention."""
    messages: Annotated[list, add_messages]
    code_files: list[dict]
    test_results: list[dict]
    iteration: int
    max_iterations: int
    consecutive_failures: int
    exit_reason: str | None


def check_exit_conditions(state: SwarmState) -> str:
    """Check if swarm should exit."""
    
    # Max iterations reached
    if state.get("iteration", 0) >= state.get("max_iterations", 10):
        return "max_iterations"
    
    # Too many consecutive failures
    if state.get("consecutive_failures", 0) >= 3:
        return "stuck_in_loop"
    
    # All tests passing
    test_results = state.get("test_results", [])
    if test_results:
        all_passed = all(t["status"] == "passed" for t in test_results)
        if all_passed:
            return "tests_passed"
    
    return "continue"


def create_swarm_with_exit_conditions():
    """Create swarm with proper exit conditions."""
    
    builder = StateGraph(SwarmState)
    
    # Add nodes
    builder.add_node("coding_agent", coding_agent_node)
    builder.add_node("testing_agent", testing_agent_node)
    builder.add_node("exit_checker", exit_checker_node)
    
    # Entry
    builder.add_edge(START, "coding_agent")
    
    # Coding goes to testing
    builder.add_edge("coding_agent", "testing_agent")
    
    # Testing goes to exit checker
    builder.add_edge("testing_agent", "exit_checker")
    
    # Exit checker routes
    builder.add_conditional_edges(
        "exit_checker",
        check_exit_conditions,
        {
            "continue": "coding_agent",
            "tests_passed": END,
            "max_iterations": "human_intervention",
            "stuck_in_loop": "human_intervention",
        }
    )
    
    # Human intervention uses interrupt
    builder.add_node("human_intervention", human_intervention_node)
    builder.add_edge("human_intervention", END)
    
    return builder.compile()


async def human_intervention_node(state: SwarmState) -> dict:
    """Request human intervention when stuck."""
    
    decision = interrupt({
        "type": "intervention_required",
        "reason": state.get("exit_reason"),
        "iterations": state.get("iteration"),
        "last_failures": state.get("test_results", [])[-3:],
        "options": ["continue", "abort", "modify_approach"]
    })
    
    if decision["action"] == "abort":
        return {"exit_reason": "human_abort"}
    elif decision["action"] == "continue":
        return {
            "max_iterations": state.get("max_iterations", 10) + 5,
            "consecutive_failures": 0
        }
    else:
        return {"exit_reason": "needs_modification"}
```

---

## 6. Checkpointing and Persistence

### 6.1 PostgresSaver Configuration

```python
# src/agent/langgraph/persistence.py

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
import os


class SDLCCheckpointer:
    """Manages checkpoint persistence for SDLC workflows."""
    
    def __init__(
        self,
        connection_string: str | None = None,
        pool_min_size: int = 5,
        pool_max_size: int = 20,
    ):
        """Initialize checkpointer with connection pool.
        
        Args:
            connection_string: PostgreSQL connection string
            pool_min_size: Minimum pool connections
            pool_max_size: Maximum pool connections
        """
        self.connection_string = connection_string or os.getenv(
            "POSTGRES_URL",
            "postgresql://agent:agent@localhost:5432/sdlc_agent"
        )
        
        self.pool = ConnectionPool(
            conninfo=self.connection_string,
            min_size=pool_min_size,
            max_size=pool_max_size,
        )
        
        self.checkpointer = PostgresSaver(self.pool)
    
    async def setup(self):
        """Initialize checkpoint tables in PostgreSQL."""
        async with self.pool.connection() as conn:
            await self.checkpointer.setup()
            
            # Create additional indexes for efficient queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_ts
                ON checkpoints (thread_id, checkpoint_ts DESC);
                
                CREATE INDEX IF NOT EXISTS idx_checkpoints_metadata
                ON checkpoints USING gin (metadata jsonb_path_ops);
                
                CREATE INDEX IF NOT EXISTS idx_checkpoints_project
                ON checkpoints ((metadata->>'project_id'));
            """)
    
    def get_checkpointer(self) -> PostgresSaver:
        """Get the PostgresSaver instance for graph compilation."""
        return self.checkpointer
    
    async def list_threads_for_project(self, project_id: str) -> list[dict]:
        """List all threads for a specific project."""
        async with self.pool.connection() as conn:
            result = await conn.execute("""
                SELECT DISTINCT thread_id, 
                       MIN(checkpoint_ts) as started_at,
                       MAX(checkpoint_ts) as last_updated
                FROM checkpoints
                WHERE metadata->>'project_id' = $1
                GROUP BY thread_id
                ORDER BY last_updated DESC
            """, [project_id])
            return [dict(row) for row in await result.fetchall()]
    
    async def get_thread_state(self, thread_id: str) -> dict | None:
        """Get current state for a thread."""
        config = {"configurable": {"thread_id": thread_id}}
        return await self.checkpointer.aget(config)
    
    async def delete_thread(self, thread_id: str):
        """Delete all checkpoints for a thread."""
        async with self.pool.connection() as conn:
            await conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = $1",
                [thread_id]
            )
    
    async def close(self):
        """Close the connection pool."""
        await self.pool.close()


# Usage example
async def main():
    checkpointer = SDLCCheckpointer()
    await checkpointer.setup()
    
    # Compile graph with checkpointer
    graph = create_sdlc_orchestrator(llm, checkpointer.get_checkpointer())
    
    # Execute with thread_id
    config = {"configurable": {"thread_id": "project-123-workflow-1"}}
    result = await graph.ainvoke(initial_state, config)
```

### 6.2 Thread-based Session Management

```python
# src/agent/langgraph/session.py

from datetime import datetime
import uuid


class SessionManager:
    """Manages workflow sessions using checkpoint threads."""
    
    def __init__(self, checkpointer: SDLCCheckpointer):
        self.checkpointer = checkpointer
    
    def create_thread_id(self, project_id: str) -> str:
        """Create a unique thread ID for a new session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{project_id}_{timestamp}_{unique_id}"
    
    async def start_session(
        self,
        project_id: str,
        project_name: str,
        initial_message: str
    ) -> tuple[str, dict]:
        """Start a new workflow session.
        
        Returns:
            Tuple of (thread_id, config)
        """
        thread_id = self.create_thread_id(project_id)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "sdlc_workflow",
            },
            "metadata": {
                "project_id": project_id,
                "project_name": project_name,
                "started_at": datetime.now().isoformat(),
            }
        }
        
        return thread_id, config
    
    async def resume_session(self, thread_id: str) -> tuple[dict | None, dict]:
        """Resume an existing session.
        
        Returns:
            Tuple of (existing_state, config)
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.checkpointer.get_thread_state(thread_id)
        return state, config
    
    async def list_project_sessions(self, project_id: str) -> list[dict]:
        """List all sessions for a project."""
        return await self.checkpointer.list_threads_for_project(project_id)
```

### 6.3 Durability Modes

```python
# Configure durability based on requirements

from langgraph.checkpoint.postgres import PostgresSaver

# Full durability - every step is persisted
# Use for production workflows requiring recovery
full_saver = PostgresSaver(
    pool,
    serde=None,  # Use default JSON serialization
)

# Compile with full durability
graph_full = builder.compile(
    checkpointer=full_saver,
    # Additional options
    interrupt_before=["human_approval"],  # Pause before approval nodes
    interrupt_after=["deployment_agent"],  # Pause after deployment
)


# Async durability - persist asynchronously for better performance
# checkpoint writes don't block execution
# Note: May lose state if process crashes before write completes

# Exit-only durability - only persist at interrupts and completion
# Best performance, but cannot resume mid-execution
```

### 6.4 Recovery from Failures

```python
# src/agent/langgraph/recovery.py

from langgraph.types import Command


async def recover_workflow(
    graph,
    checkpointer: SDLCCheckpointer,
    thread_id: str
) -> dict:
    """Recover a workflow from its last checkpoint.
    
    Args:
        graph: Compiled StateGraph
        checkpointer: Checkpoint manager
        thread_id: Thread to recover
        
    Returns:
        Final state after recovery
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    # Get last checkpoint state
    state = await checkpointer.get_thread_state(thread_id)
    
    if not state:
        raise ValueError(f"No checkpoint found for thread {thread_id}")
    
    # Check if workflow was interrupted
    if "__interrupt__" in state:
        interrupt_info = state["__interrupt__"]
        print(f"Workflow interrupted at: {interrupt_info}")
        
        # Handle based on interrupt type
        if interrupt_info[0].value.get("type") == "approval_request":
            # Need human input to resume
            raise InterruptedWorkflowError(
                "Workflow requires human approval to continue",
                interrupt_info
            )
    
    # Check error state
    if state.get("errors"):
        last_error = state["errors"][-1]
        print(f"Last error: {last_error}")
        
        # Reset retry count and continue
        state["retry_count"] = 0
    
    # Resume execution
    result = await graph.ainvoke(None, config)
    
    return result


class InterruptedWorkflowError(Exception):
    """Raised when workflow requires human intervention."""
    
    def __init__(self, message: str, interrupt_info: list):
        super().__init__(message)
        self.interrupt_info = interrupt_info
```

---

## 7. Human-in-the-Loop Gates

### 7.1 Using interrupt() Function

```python
# src/agent/langgraph/approval.py

from langgraph.types import interrupt, Command
from typing import Literal, TypedDict

# Define approval gates for each SDLC phase
APPROVAL_GATES = {
    "requirements": ["prd_approval", "user_story_approval"],
    "system_design": ["schema_approval", "api_spec_approval"],
    "architecture": ["tech_stack_approval", "security_review"],
    "implementation": ["code_review", "merge_approval"],
    "deployment": ["staging_approval", "production_approval"],
    "monitoring": ["alert_config_approval"],
}


async def create_approval_request(
    state: SDLCState,
    gate: str,
    artifact_id: str,
    summary: str,
    details: dict | None = None
) -> dict:
    """Create an approval request and interrupt workflow.
    
    Args:
        state: Current workflow state
        gate: Approval gate identifier
        artifact_id: ID of artifact requiring approval
        summary: Human-readable summary
        details: Additional context for reviewer
        
    Returns:
        Decision from human reviewer
    """
    
    # Interrupt and wait for human decision
    decision = interrupt({
        "type": "approval_request",
        "gate": gate,
        "phase": state.get("current_phase"),
        "artifact_id": artifact_id,
        "summary": summary,
        "details": details or {},
        "options": ["approve", "reject", "request_changes"],
        "requested_at": datetime.now().isoformat(),
    })
    
    return decision
```

### 7.2 Approval Gate Patterns

```python
# src/agent/langgraph/nodes/approval_gate.py

from langgraph.types import interrupt, Command
from typing import Literal


class ApprovalDecision(TypedDict):
    """Structure of human approval decision."""
    action: Literal["approve", "reject", "request_changes"]
    feedback: str | None
    approved_by: str | None
    timestamp: str


async def human_approval_node(state: SDLCState) -> Command[Literal["proceed", "revise", "abort"]]:
    """Handle human approval gates with Command routing.
    
    This node interrupts execution, presents the approval request to a human,
    and routes to the appropriate next node based on their decision.
    """
    
    pending = state.get("pending_approvals", [])
    
    if not pending:
        # No approvals needed, continue
        return Command(goto="proceed")
    
    approval_request = pending[0]
    
    # Interrupt and wait for human decision
    decision: ApprovalDecision = interrupt({
        "type": "approval_request",
        "gate": approval_request["gate"],
        "phase": approval_request["phase"],
        "artifact": approval_request["artifact_id"],
        "summary": approval_request["summary"],
        "details": approval_request.get("details", {}),
        "options": ["approve", "reject", "request_changes"],
    })
    
    # Process decision and route accordingly
    if decision["action"] == "approve":
        # Remove from pending, add to approved
        new_pending = pending[1:]
        new_approved = state.get("approved_items", []) + [approval_request["artifact_id"]]
        
        return Command(
            goto="proceed",
            update={
                "pending_approvals": new_pending,
                "approved_items": new_approved,
            }
        )
    
    elif decision["action"] == "reject":
        return Command(
            goto="abort",
            update={
                "rejected_items": state.get("rejected_items", []) + [approval_request["artifact_id"]],
                "errors": state.get("errors", []) + [{
                    "type": "approval_rejected",
                    "gate": approval_request["gate"],
                    "reason": decision.get("feedback", "No reason provided"),
                }],
                "phase_status": "failed",
            }
        )
    
    else:  # request_changes
        return Command(
            goto="revise",
            update={
                "messages": state.get("messages", []) + [{
                    "role": "user",
                    "content": f"Changes requested: {decision.get('feedback', 'Please revise')}",
                    "agent_id": None,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"change_request": True, "gate": approval_request["gate"]}
                }],
                "phase_status": "blocked",
            }
        )


# Build graph with approval gates
builder = StateGraph(SDLCState)

builder.add_node("work", worker_node)
builder.add_node("approval", human_approval_node)
builder.add_node("proceed", proceed_node)
builder.add_node("revise", revision_node)
builder.add_node("abort", abort_node)

builder.add_edge(START, "work")
builder.add_edge("work", "approval")

# Approval node uses Command to route
builder.add_edge("proceed", END)
builder.add_edge("revise", "work")
builder.add_edge("abort", END)
```

### 7.3 Feedback Incorporation via Command

```python
# Resuming with feedback

from langgraph.types import Command

async def resume_with_approval(
    graph,
    thread_id: str,
    decision: ApprovalDecision
):
    """Resume workflow with human approval decision.
    
    Args:
        graph: Compiled workflow graph
        thread_id: Thread to resume
        decision: Human's approval decision
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    # Resume with the decision
    result = await graph.ainvoke(
        Command(resume=decision),
        config
    )
    
    return result


# Example: Approve with feedback
result = await resume_with_approval(
    graph,
    "project-123-workflow-1",
    {
        "action": "approve",
        "feedback": "Looks good, but add more error handling",
        "approved_by": "tech-lead@company.com",
        "timestamp": datetime.now().isoformat(),
    }
)

# Example: Request changes
result = await resume_with_approval(
    graph,
    "project-123-workflow-1",
    {
        "action": "request_changes",
        "feedback": "Please add unit tests for edge cases",
        "approved_by": "qa-engineer@company.com",
        "timestamp": datetime.now().isoformat(),
    }
)
```

---

## 8. Parallel Execution

### 8.1 Using Send API for Fan-out

```python
# src/agent/langgraph/parallel.py

from langgraph.types import Send
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import operator


class ParallelState(TypedDict):
    """State for parallel execution patterns."""
    tasks: list[dict]
    results: Annotated[list[dict], operator.add]
    final_output: str


class WorkerInput(TypedDict):
    """Input state for individual workers."""
    task: dict
    worker_id: str


def create_parallel_workflow():
    """Create a workflow with parallel task execution."""
    
    builder = StateGraph(ParallelState)
    
    # Orchestrator creates parallel tasks
    builder.add_node("orchestrator", orchestrator_node)
    
    # Worker processes individual tasks
    builder.add_node("worker", worker_node)
    
    # Synthesizer combines results
    builder.add_node("synthesizer", synthesizer_node)
    
    # Define flow
    builder.add_edge(START, "orchestrator")
    
    # Fan-out: orchestrator sends to multiple workers
    builder.add_conditional_edges(
        "orchestrator",
        create_worker_sends,
        ["worker"]  # All sends go to worker node
    )
    
    # Workers converge at synthesizer
    builder.add_edge("worker", "synthesizer")
    
    builder.add_edge("synthesizer", END)
    
    return builder.compile()


def orchestrator_node(state: ParallelState) -> dict:
    """Orchestrator creates tasks for parallel execution."""
    
    # Generate tasks (e.g., code files to implement)
    tasks = [
        {"file": "src/models.py", "description": "Data models"},
        {"file": "src/api.py", "description": "API endpoints"},
        {"file": "src/services.py", "description": "Business logic"},
        {"file": "src/utils.py", "description": "Utility functions"},
    ]
    
    return {"tasks": tasks}


def create_worker_sends(state: ParallelState) -> list[Send]:
    """Create Send objects for parallel worker execution.
    
    Each Send spawns a separate worker instance with its own state.
    """
    sends = []
    
    for i, task in enumerate(state.get("tasks", [])):
        sends.append(
            Send(
                "worker",
                WorkerInput(
                    task=task,
                    worker_id=f"worker_{i}"
                )
            )
        )
    
    return sends


async def worker_node(state: WorkerInput) -> dict:
    """Worker processes a single task.
    
    Each worker runs in parallel and writes to the shared results list.
    """
    task = state["task"]
    worker_id = state["worker_id"]
    
    # Process task (e.g., generate code)
    result = {
        "worker_id": worker_id,
        "file": task["file"],
        "content": f"# Generated by {worker_id}\n# {task['description']}",
        "status": "completed",
    }
    
    # Return writes to results list (reducer handles aggregation)
    return {"results": [result]}


def synthesizer_node(state: ParallelState) -> dict:
    """Combine results from all parallel workers."""
    
    results = state.get("results", [])
    
    summary = f"Completed {len(results)} files:\n"
    for r in results:
        summary += f"- {r['file']}: {r['status']}\n"
    
    return {"final_output": summary}
```

### 8.2 Parallel Coding Workers

```python
# src/agent/langgraph/parallel_coding.py

from langgraph.types import Send


class CodingTask(TypedDict):
    """Task for a coding worker."""
    file_path: str
    purpose: str
    interfaces: list[str]
    dependencies: list[str]


class CodingWorkerState(TypedDict):
    """State for individual coding worker."""
    task: CodingTask
    architecture: dict
    code_files: Annotated[list[CodeFile], operator.add]


async def coding_orchestrator(state: SDLCState) -> list[Send]:
    """Create parallel coding tasks from architecture spec.
    
    Analyzes the architecture and creates one Send per file to implement.
    """
    architecture = state.get("artifacts", {}).get("architecture", {})
    file_specs = architecture.get("file_specifications", [])
    
    sends = []
    for i, spec in enumerate(file_specs):
        sends.append(
            Send(
                "coding_worker",
                CodingWorkerState(
                    task=CodingTask(
                        file_path=spec["path"],
                        purpose=spec["purpose"],
                        interfaces=spec.get("interfaces", []),
                        dependencies=spec.get("dependencies", []),
                    ),
                    architecture=architecture,
                    code_files=[],
                )
            )
        )
    
    return sends


async def coding_worker(state: CodingWorkerState) -> dict:
    """Individual coding worker generates one file."""
    
    task = state["task"]
    architecture = state["architecture"]
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    
    prompt = f"""Generate production-quality code for:
    
    File: {task['file_path']}
    Purpose: {task['purpose']}
    
    Interfaces to implement: {task['interfaces']}
    Dependencies: {task['dependencies']}
    
    Architecture context:
    {json.dumps(architecture, indent=2)[:2000]}
    """
    
    response = await llm.ainvoke(prompt)
    
    code_file = CodeFile(
        path=task["file_path"],
        content=response.content,
        language=task["file_path"].split(".")[-1],
        imports=[],  # Parse from response
        exports=[],  # Parse from response
        checksum=hashlib.md5(response.content.encode()).hexdigest(),
    )
    
    return {"code_files": [code_file]}
```

### 8.3 Result Aggregation with Reducers

```python
# Custom reducers for complex aggregation

def aggregate_code_files(existing: list[CodeFile], new: list[CodeFile]) -> list[CodeFile]:
    """Aggregate code files, handling conflicts by path.
    
    If multiple workers produce the same file path, keep the latest version.
    """
    files_by_path = {f["path"]: f for f in existing}
    
    for file in new:
        files_by_path[file["path"]] = file
    
    return list(files_by_path.values())


def aggregate_test_results(existing: list[TestResult], new: list[TestResult]) -> list[TestResult]:
    """Aggregate test results, keeping latest run per test."""
    
    results_by_name = {}
    
    for result in existing + new:
        key = f"{result['test_file']}::{result['test_name']}"
        # Keep latest result (last one wins)
        results_by_name[key] = result
    
    return list(results_by_name.values())


# Use in state definition
class SDLCState(TypedDict):
    code_files: Annotated[list[CodeFile], aggregate_code_files]
    test_results: Annotated[list[TestResult], aggregate_test_results]
```

---

## 9. Error Handling and Retry

### 9.1 RetryPolicy Configuration

```python
# src/agent/langgraph/retry.py

from dataclasses import dataclass
from typing import Callable, Any
import asyncio


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retry_on: tuple[type[Exception], ...] = (Exception,)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt number."""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


async def with_retry(
    func: Callable,
    policy: RetryPolicy,
    *args,
    **kwargs
) -> Any:
    """Execute function with retry policy.
    
    Args:
        func: Async function to execute
        policy: Retry configuration
        *args, **kwargs: Function arguments
        
    Returns:
        Function result
        
    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None
    
    for attempt in range(policy.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except policy.retry_on as e:
            last_exception = e
            
            if attempt < policy.max_retries:
                delay = policy.get_delay(attempt)
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
    
    raise last_exception


# Usage in node
async def llm_node_with_retry(state: SDLCState) -> dict:
    """Node that retries LLM calls on failure."""
    
    policy = RetryPolicy(
        max_retries=3,
        initial_delay=1.0,
        retry_on=(RateLimitError, TimeoutError, APIError),
    )
    
    async def call_llm():
        response = await llm.ainvoke(messages)
        return response.content
    
    result = await with_retry(call_llm, policy)
    
    return {"output": result}
```

### 9.2 Circuit Breakers

```python
# src/agent/langgraph/circuit_breaker.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for failing services."""
    
    failure_threshold: int = 5
    recovery_timeout: timedelta = timedelta(seconds=30)
    half_open_max_calls: int = 3
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: datetime | None = None
    half_open_calls: int = 0
    
    def can_execute(self) -> bool:
        """Check if request can proceed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery period has passed
            if self.last_failure_time:
                elapsed = datetime.now() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        
        return False
    
    def record_success(self):
        """Record successful execution."""
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.half_open_max_calls:
                # Recovered, close circuit
                self.state = CircuitState.CLOSED
                self.failure_count = 0
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.success_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery, open circuit
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            # Too many failures, open circuit
            self.state = CircuitState.OPEN


# Usage in workflow
circuits = {
    "openai": CircuitBreaker(failure_threshold=5),
    "anthropic": CircuitBreaker(failure_threshold=5),
}


async def llm_with_circuit_breaker(state: SDLCState) -> dict:
    """LLM call with circuit breaker protection."""
    
    primary_circuit = circuits["openai"]
    fallback_circuit = circuits["anthropic"]
    
    # Try primary
    if primary_circuit.can_execute():
        try:
            result = await openai_llm.ainvoke(messages)
            primary_circuit.record_success()
            return {"output": result.content}
        except Exception as e:
            primary_circuit.record_failure()
    
    # Try fallback
    if fallback_circuit.can_execute():
        try:
            result = await anthropic_llm.ainvoke(messages)
            fallback_circuit.record_success()
            return {"output": result.content}
        except Exception as e:
            fallback_circuit.record_failure()
    
    # Both circuits open
    return {
        "errors": [{
            "type": "circuit_breaker_open",
            "message": "All LLM providers unavailable",
        }]
    }
```

### 9.3 Fallback Model Routing

```python
# src/agent/langgraph/fallback.py

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


class ModelRouter:
    """Routes to fallback models on failure."""
    
    def __init__(self):
        self.models = [
            ChatOpenAI(model="gpt-4o", timeout=30),
            ChatOpenAI(model="gpt-4o-mini", timeout=30),
            ChatAnthropic(model="claude-3-5-sonnet-20241022", timeout=30),
        ]
        self.current_index = 0
    
    async def invoke(self, messages: list) -> str:
        """Invoke with fallback to other models."""
        errors = []
        
        for i, model in enumerate(self.models):
            try:
                response = await model.ainvoke(messages)
                self.current_index = i  # Remember successful model
                return response.content
            except Exception as e:
                errors.append(f"{model.model}: {str(e)}")
                continue
        
        raise Exception(f"All models failed: {errors}")


# Usage
router = ModelRouter()


async def resilient_llm_node(state: SDLCState) -> dict:
    """Node with automatic model fallback."""
    messages = state.get("messages", [])
    
    try:
        output = await router.invoke(messages)
        return {"output": output}
    except Exception as e:
        return {
            "errors": [{"type": "all_models_failed", "message": str(e)}],
            "phase_status": "failed",
        }
```

### 9.4 Loop Detection and max_steps

```python
# src/agent/langgraph/loop_detection.py


def create_loop_protected_graph(max_steps: int = 100):
    """Create graph with loop detection and step limits."""
    
    builder = StateGraph(SDLCState)
    
    # Add step tracking node
    def track_steps(state: SDLCState) -> dict:
        iteration = state.get("iteration", 0) + 1
        max_iter = state.get("max_iterations", max_steps)
        
        if iteration > max_iter:
            return {
                "errors": [{
                    "type": "max_iterations_exceeded",
                    "iterations": iteration,
                    "limit": max_iter,
                }],
                "phase_status": "failed",
            }
        
        return {"iteration": iteration}
    
    # Add loop detection
    def detect_loop(state: SDLCState) -> str:
        """Detect if workflow is stuck in a loop."""
        messages = state.get("messages", [])
        
        # Check for repeated patterns in last N messages
        if len(messages) >= 6:
            recent = [m.content[:100] for m in messages[-6:]]
            
            # Check for AAA pattern
            if len(set(recent[-3:])) == 1:
                return "loop_detected"
            
            # Check for ABABAB pattern
            if recent[-1] == recent[-3] == recent[-5] and recent[-2] == recent[-4]:
                return "loop_detected"
        
        return "continue"
    
    builder.add_node("step_tracker", track_steps)
    builder.add_node("work", worker_node)
    builder.add_node("loop_handler", loop_handler_node)
    
    builder.add_edge(START, "step_tracker")
    builder.add_conditional_edges(
        "step_tracker",
        lambda s: "error" if s.get("errors") else "continue",
        {"error": END, "continue": "work"}
    )
    
    builder.add_conditional_edges(
        "work",
        detect_loop,
        {"loop_detected": "loop_handler", "continue": "step_tracker"}
    )
    
    builder.add_edge("loop_handler", END)
    
    return builder.compile()


async def loop_handler_node(state: SDLCState) -> dict:
    """Handle detected loops with human intervention."""
    
    decision = interrupt({
        "type": "loop_detected",
        "message": "Workflow appears stuck in a loop",
        "recent_actions": [m.content[:100] for m in state.get("messages", [])[-6:]],
        "options": ["abort", "reset", "continue_with_different_approach"],
    })
    
    if decision["action"] == "abort":
        return {"phase_status": "failed", "errors": [{"type": "loop_aborted"}]}
    elif decision["action"] == "reset":
        return {"iteration": 0, "messages": []}
    else:
        return {
            "messages": [{
                "role": "user",
                "content": f"Previous approach was looping. Try: {decision.get('new_approach', 'a different strategy')}",
            }]
        }
```

---

## 10. Complete SDLC Graph Definition

### 10.1 Full StateGraph Code Example

```python
# src/agent/langgraph/sdlc_workflow.py

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_openai import ChatOpenAI

from agent.langgraph.state import SDLCState
from agent.langgraph.nodes import (
    requirements_node,
    system_design_node,
    architecture_node,
    coding_orchestrator_node,
    coding_worker_node,
    testing_node,
    cicd_node,
    deployment_node,
    monitoring_node,
    human_approval_node,
    error_handler_node,
)


def create_complete_sdlc_workflow(
    llm: ChatOpenAI,
    checkpointer: PostgresSaver,
) -> StateGraph:
    """Create the complete SDLC workflow graph.
    
    This graph implements the full software development lifecycle with:
    - Sequential phase execution
    - Parallel coding workers
    - Human approval gates
    - Error handling and retry
    - Checkpoint persistence
    
    Args:
        llm: LLM client for agent reasoning
        checkpointer: PostgreSQL checkpoint saver
        
    Returns:
        Compiled StateGraph ready for execution
    """
    
    builder = StateGraph(SDLCState)
    
    # ===== Add all nodes =====
    
    # Phase worker nodes
    builder.add_node("requirements", requirements_node)
    builder.add_node("system_design", system_design_node)
    builder.add_node("architecture", architecture_node)
    builder.add_node("coding_orchestrator", coding_orchestrator_node)
    builder.add_node("coding_worker", coding_worker_node)
    builder.add_node("testing", testing_node)
    builder.add_node("cicd", cicd_node)
    builder.add_node("deployment", deployment_node)
    builder.add_node("monitoring", monitoring_node)
    
    # Control nodes
    builder.add_node("supervisor", create_supervisor_node(llm))
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("error_handler", error_handler_node)
    builder.add_node("phase_complete", phase_complete_node)
    
    # ===== Define edges =====
    
    # Entry point
    builder.add_edge(START, "supervisor")
    
    # Supervisor routing
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "requirements": "requirements",
            "system_design": "system_design",
            "architecture": "architecture",
            "implementation": "coding_orchestrator",
            "testing": "testing",
            "ci_cd": "cicd",
            "deployment": "deployment",
            "monitoring": "monitoring",
            "approval_needed": "human_approval",
            "error": "error_handler",
            "complete": END,
        }
    )
    
    # Phase nodes go to approval check
    for phase in ["requirements", "system_design", "architecture", "testing", "cicd", "deployment", "monitoring"]:
        builder.add_conditional_edges(
            phase,
            check_needs_approval,
            {
                "needs_approval": "human_approval",
                "continue": "phase_complete",
                "error": "error_handler",
            }
        )
    
    # Coding orchestrator fans out to workers
    builder.add_conditional_edges(
        "coding_orchestrator",
        create_coding_workers,
        ["coding_worker"]
    )
    
    # Coding workers converge back
    builder.add_conditional_edges(
        "coding_worker",
        check_needs_approval,
        {
            "needs_approval": "human_approval",
            "continue": "phase_complete",
            "error": "error_handler",
        }
    )
    
    # Human approval routing (uses Command)
    # approval node returns Command(goto=...) for routing
    
    # Phase complete returns to supervisor
    builder.add_edge("phase_complete", "supervisor")
    
    # Error handler can retry or escalate
    builder.add_conditional_edges(
        "error_handler",
        route_after_error,
        {
            "retry": "supervisor",
            "escalate": "human_approval",
            "abort": END,
        }
    )
    
    # ===== Compile with checkpointer =====
    
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_approval"],  # Allows state inspection before approval
    )


# ===== Routing functions =====

def route_from_supervisor(state: SDLCState) -> str:
    """Route based on supervisor decision."""
    
    # Check for errors first
    if state.get("errors") and state.get("retry_count", 0) >= state.get("max_retries", 3):
        return "error"
    
    # Check for pending approvals
    if state.get("pending_approvals"):
        return "approval_needed"
    
    # Route to next agent
    next_agent = state.get("next_agent")
    if next_agent == "complete":
        return "complete"
    
    # Map phase to implementation node
    phase_mapping = {
        "requirements": "requirements",
        "system_design": "system_design",
        "architecture": "architecture",
        "implementation": "implementation",
        "testing": "testing",
        "ci_cd": "ci_cd",
        "deployment": "deployment",
        "monitoring": "monitoring",
    }
    
    return phase_mapping.get(state.get("current_phase"), "complete")


def check_needs_approval(state: SDLCState) -> str:
    """Check if current phase needs human approval."""
    
    if state.get("errors"):
        return "error"
    
    if state.get("pending_approvals"):
        return "needs_approval"
    
    return "continue"


def route_after_error(state: SDLCState) -> str:
    """Route after error handling."""
    
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count < max_retries:
        return "retry"
    
    # Check if error requires human intervention
    last_error = state.get("errors", [{}])[-1]
    if last_error.get("type") in ["approval_rejected", "loop_detected"]:
        return "escalate"
    
    return "abort"


# ===== Control nodes =====

def create_supervisor_node(llm: ChatOpenAI):
    """Create the supervisor node."""
    
    async def supervisor(state: SDLCState) -> dict:
        """Supervisor analyzes state and decides next step."""
        
        current_phase = state.get("current_phase", "requirements")
        phase_status = state.get("phase_status", "pending")
        
        # If phase completed, advance to next
        if phase_status == "completed":
            phases = [
                "requirements", "system_design", "architecture",
                "implementation", "testing", "ci_cd",
                "deployment", "monitoring"
            ]
            current_idx = phases.index(current_phase)
            
            if current_idx >= len(phases) - 1:
                return {
                    "next_agent": "complete",
                    "routing_reason": "All phases completed successfully",
                }
            
            next_phase = phases[current_idx + 1]
            return {
                "current_phase": next_phase,
                "phase_status": "in_progress",
                "next_agent": next_phase,
                "routing_reason": f"Advancing to {next_phase} phase",
            }
        
        # Continue with current phase
        return {
            "next_agent": current_phase,
            "phase_status": "in_progress",
            "routing_reason": f"Continuing {current_phase} phase",
        }
    
    return supervisor


async def phase_complete_node(state: SDLCState) -> dict:
    """Mark current phase as complete."""
    
    current_phase = state.get("current_phase")
    completed = state.get("completed_phases", [])
    
    return {
        "phase_status": "completed",
        "completed_phases": completed + [current_phase],
        "last_updated_at": datetime.now().isoformat(),
    }


async def error_handler_node(state: SDLCState) -> dict:
    """Handle errors and decide retry strategy."""
    
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)
    
    if not errors:
        return {}
    
    last_error = errors[-1]
    
    # Log error
    print(f"Error in phase {state.get('current_phase')}: {last_error}")
    
    return {
        "retry_count": retry_count + 1,
        "phase_status": "pending",  # Reset for retry
    }
```

### 10.2 Node Functions for Each SDLC Phase

```python
# src/agent/langgraph/nodes/__init__.py

from .requirements import requirements_node
from .system_design import system_design_node
from .architecture import architecture_node
from .coding import coding_orchestrator_node, coding_worker_node
from .testing import testing_node
from .cicd import cicd_node
from .deployment import deployment_node
from .monitoring import monitoring_node
from .approval import human_approval_node
from .error_handler import error_handler_node

__all__ = [
    "requirements_node",
    "system_design_node",
    "architecture_node",
    "coding_orchestrator_node",
    "coding_worker_node",
    "testing_node",
    "cicd_node",
    "deployment_node",
    "monitoring_node",
    "human_approval_node",
    "error_handler_node",
]
```

See individual node implementations in sections above for detailed code.

### 10.3 Edge Definitions and Conditions

The following diagram shows the complete edge structure:

```mermaid
graph TB
    START --> supervisor
    
    supervisor --> |requirements| requirements
    supervisor --> |system_design| system_design
    supervisor --> |architecture| architecture
    supervisor --> |implementation| coding_orchestrator
    supervisor --> |testing| testing
    supervisor --> |ci_cd| cicd
    supervisor --> |deployment| deployment
    supervisor --> |monitoring| monitoring
    supervisor --> |approval_needed| human_approval
    supervisor --> |error| error_handler
    supervisor --> |complete| END
    
    requirements --> |needs_approval| human_approval
    requirements --> |continue| phase_complete
    requirements --> |error| error_handler
    
    system_design --> |needs_approval| human_approval
    system_design --> |continue| phase_complete
    
    architecture --> |needs_approval| human_approval
    architecture --> |continue| phase_complete
    
    coding_orchestrator --> |Send| coding_worker
    coding_worker --> |needs_approval| human_approval
    coding_worker --> |continue| phase_complete
    
    testing --> |needs_approval| human_approval
    testing --> |continue| phase_complete
    
    cicd --> |continue| phase_complete
    deployment --> |needs_approval| human_approval
    deployment --> |continue| phase_complete
    monitoring --> |continue| phase_complete
    
    phase_complete --> supervisor
    
    human_approval --> |Command| proceed_or_revise
    
    error_handler --> |retry| supervisor
    error_handler --> |escalate| human_approval
    error_handler --> |abort| END
```

### 10.4 Compilation with Checkpointer

```python
# src/agent/langgraph/compile.py

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool


async def compile_sdlc_workflow():
    """Compile the SDLC workflow with production settings."""
    
    # Initialize connection pool
    pool = ConnectionPool(
        conninfo="postgresql://agent:agent@localhost:5432/sdlc_agent",
        min_size=5,
        max_size=20,
    )
    
    # Create checkpointer
    checkpointer = PostgresSaver(pool)
    await checkpointer.setup()  # Create tables if not exist
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    # Compile workflow
    workflow = create_complete_sdlc_workflow(llm, checkpointer)
    
    return workflow


# Executing the workflow
async def run_sdlc_workflow(
    project_id: str,
    project_name: str,
    initial_requirements: str,
):
    """Run the complete SDLC workflow for a project."""
    
    workflow = await compile_sdlc_workflow()
    
    # Create thread for this project run
    thread_id = f"{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Initial state
    initial_state = SDLCState(
        messages=[HumanMessage(content=initial_requirements)],
        project_id=project_id,
        project_name=project_name,
        project_path=f"/workspace/{project_id}",
        current_phase="requirements",
        phase_status="pending",
        completed_phases=[],
        artifacts={},
        code_files=[],
        test_results=[],
        pending_approvals=[],
        approved_items=[],
        rejected_items=[],
        errors=[],
        retry_count=0,
        max_retries=3,
        next_agent=None,
        routing_reason=None,
        active_agent="supervisor",
        iteration=0,
        max_iterations=100,
        started_at=datetime.now().isoformat(),
        last_updated_at=datetime.now().isoformat(),
    )
    
    # Execute with streaming for real-time updates
    final_state = None
    async for event in workflow.astream(initial_state, config):
        print(f"Event: {event}")
        
        # Check for interrupts (human approval needed)
        if "__interrupt__" in event:
            print(f"Workflow interrupted: {event['__interrupt__']}")
            # In production, notify user and wait for input
            break
        
        final_state = event
    
    return final_state, thread_id
```

---

## 11. Testing LangGraph Workflows

### 11.1 Unit Testing Nodes

```python
# tests/unit/test_nodes.py

import pytest
from unittest.mock import AsyncMock, patch

from agent.langgraph.state import SDLCState
from agent.langgraph.nodes.requirements import requirements_node


@pytest.fixture
def sample_state() -> SDLCState:
    """Create a sample state for testing."""
    return SDLCState(
        messages=[{"role": "user", "content": "Build a todo app"}],
        project_id="test-project",
        project_name="Test Todo App",
        project_path="/workspace/test-project",
        current_phase="requirements",
        phase_status="pending",
        completed_phases=[],
        artifacts={},
        code_files=[],
        test_results=[],
        pending_approvals=[],
        approved_items=[],
        rejected_items=[],
        errors=[],
        retry_count=0,
        max_retries=3,
        next_agent=None,
        routing_reason=None,
        active_agent="requirements_agent",
        iteration=0,
        max_iterations=100,
        started_at="2026-02-06T00:00:00Z",
        last_updated_at="2026-02-06T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_requirements_node_generates_prd(sample_state):
    """Test that requirements node generates PRD artifacts."""
    
    with patch("agent.langgraph.nodes.requirements.ChatOpenAI") as mock_llm:
        # Mock LLM response
        mock_llm.return_value.ainvoke = AsyncMock(
            return_value=Mock(content="# PRD\n\n## Overview\nTodo application...")
        )
        
        result = await requirements_node(sample_state)
        
        # Verify PRD was generated
        assert "artifacts" in result
        assert "requirements" in result["artifacts"]
        assert "prd" in result["artifacts"]["requirements"]
        
        # Verify approval was requested
        assert "pending_approvals" in result
        assert len(result["pending_approvals"]) == 1
        assert result["pending_approvals"][0]["gate"] == "prd_approval"


@pytest.mark.asyncio
async def test_requirements_node_handles_llm_error(sample_state):
    """Test that requirements node handles LLM errors gracefully."""
    
    with patch("agent.langgraph.nodes.requirements.ChatOpenAI") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )
        
        result = await requirements_node(sample_state)
        
        # Should add error to state
        assert "errors" in result
        assert len(result["errors"]) == 1
        assert "LLM unavailable" in str(result["errors"][0])
```

### 11.2 Integration Testing the Full Graph

```python
# tests/integration/test_workflow.py

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent.langgraph.sdlc_workflow import create_complete_sdlc_workflow
from agent.langgraph.state import SDLCState


@pytest.fixture
def test_workflow():
    """Create workflow with in-memory checkpointer for testing."""
    from unittest.mock import Mock
    
    mock_llm = Mock()
    checkpointer = MemorySaver()
    
    return create_complete_sdlc_workflow(mock_llm, checkpointer)


@pytest.fixture
def initial_state() -> SDLCState:
    """Create initial state for workflow testing."""
    return SDLCState(
        messages=[{"role": "user", "content": "Build a REST API"}],
        project_id="test-integration",
        project_name="Test API",
        project_path="/workspace/test",
        current_phase="requirements",
        phase_status="pending",
        completed_phases=[],
        artifacts={},
        code_files=[],
        test_results=[],
        pending_approvals=[],
        approved_items=[],
        rejected_items=[],
        errors=[],
        retry_count=0,
        max_retries=3,
        next_agent=None,
        routing_reason=None,
        active_agent="supervisor",
        iteration=0,
        max_iterations=10,
        started_at="2026-02-06T00:00:00Z",
        last_updated_at="2026-02-06T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_workflow_starts_with_supervisor(test_workflow, initial_state):
    """Test that workflow begins at supervisor node."""
    
    config = {"configurable": {"thread_id": "test-1"}}
    
    # Run one step
    result = await test_workflow.ainvoke(initial_state, config)
    
    # Should have routed to requirements phase
    assert result["current_phase"] == "requirements"
    assert result["phase_status"] == "in_progress"


@pytest.mark.asyncio
async def test_workflow_handles_interrupt(test_workflow, initial_state):
    """Test that workflow properly interrupts for human approval."""
    
    # Pre-populate with pending approval
    initial_state["pending_approvals"] = [{
        "id": "test-approval",
        "gate": "prd_approval",
        "phase": "requirements",
        "artifact_id": "requirements",
        "summary": "PRD ready",
        "details": {},
        "requested_at": "2026-02-06T00:00:00Z",
        "options": ["approve", "reject"],
    }]
    
    config = {"configurable": {"thread_id": "test-2"}}
    
    # Should interrupt at human_approval node
    result = await test_workflow.ainvoke(initial_state, config)
    
    assert "__interrupt__" in result
    assert result["__interrupt__"][0].value["gate"] == "prd_approval"


@pytest.mark.asyncio
async def test_workflow_resumes_after_approval(test_workflow, initial_state):
    """Test that workflow resumes correctly after human approval."""
    from langgraph.types import Command
    
    thread_id = "test-3"
    config = {"configurable": {"thread_id": thread_id}}
    
    # First run - should interrupt
    initial_state["pending_approvals"] = [{
        "id": "test-approval",
        "gate": "prd_approval",
        "phase": "requirements",
        "artifact_id": "requirements",
        "summary": "PRD ready",
        "details": {},
        "requested_at": "2026-02-06T00:00:00Z",
        "options": ["approve", "reject"],
    }]
    
    await test_workflow.ainvoke(initial_state, config)
    
    # Resume with approval
    result = await test_workflow.ainvoke(
        Command(resume={"action": "approve", "feedback": None}),
        config
    )
    
    # Should have processed approval
    assert "test-approval" in result.get("approved_items", []) or \
           len(result.get("pending_approvals", [])) == 0
```

### 11.3 Mocking LLM Calls

```python
# tests/conftest.py

import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns predictable responses."""
    
    mock = Mock()
    
    # Default response
    mock.ainvoke = AsyncMock(
        return_value=Mock(content="Mocked LLM response")
    )
    
    # Make it configurable
    def set_response(content: str):
        mock.ainvoke = AsyncMock(
            return_value=Mock(content=content)
        )
    
    mock.set_response = set_response
    return mock


@pytest.fixture
def mock_llm_structured():
    """Create a mock LLM with structured output."""
    
    mock = Mock()
    
    def with_structured_output(schema):
        structured_mock = Mock()
        structured_mock.invoke = Mock(
            return_value=schema(
                next_agent="requirements_agent",
                reason="Testing"
            )
        )
        return structured_mock
    
    mock.with_structured_output = with_structured_output
    return mock


# Usage in tests
@pytest.mark.asyncio
async def test_with_mocked_llm(mock_llm):
    """Test node with mocked LLM responses."""
    
    mock_llm.set_response("""# PRD
    
## Overview
This is a test PRD for the todo application.

## User Stories
- As a user, I want to create tasks
- As a user, I want to mark tasks complete
""")
    
    with patch("agent.langgraph.nodes.requirements.ChatOpenAI", return_value=mock_llm):
        result = await requirements_node(sample_state)
        
        assert "PRD" in result["artifacts"]["requirements"]["prd"]
```

---

## References

1. **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
2. **LangGraph-Swarm**: https://github.com/langchain-ai/langgraph-swarm-py
3. **SYSTEM_DESIGN.md**: [./SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md)
4. **Current ReActEngine**: [`engine.py`](../../src/agent/core/engine.py)
5. **Current Orchestrator**: [`orchestrator.py`](../../src/agent/core/orchestrator.py)
6. **Base Agent**: [`base.py`](../../src/agent/agents/base.py)

---

*Document generated for Autonomous AI Agent Framework - LangGraph Integration*
