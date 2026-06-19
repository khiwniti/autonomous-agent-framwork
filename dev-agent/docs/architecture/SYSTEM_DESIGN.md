# Autonomous AI Agent Framework - System Design Document

> **Version**: 2.0.0  
> **Status**: Architecture Design  
> **Last Updated**: 2026-02-06  
> **Target Stack**: LangGraph v1.0.7 + MCP + A2A Protocol

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [LangGraph Integration Design](#3-langgraph-integration-design)
4. [MCP Integration Design](#4-mcp-integration-design)
5. [A2A Protocol Integration](#5-a2a-protocol-integration)
6. [Sub-Agent Specifications](#6-sub-agent-specifications)
7. [Memory Architecture](#7-memory-architecture)
8. [Infrastructure Design](#8-infrastructure-design)
9. [Migration Plan](#9-migration-plan)
10. [Technology Stack Summary](#10-technology-stack-summary)

---

## 1. Executive Summary

### 1.1 Vision

This document defines the comprehensive architecture for an **Autonomous AI Agent Framework** designed for SDLC-driven SaaS builders. The system transforms the existing codebase to leverage modern agent orchestration patterns using LangGraph, universal tool integration via MCP (Model Context Protocol), and inter-agent communication through the A2A (Agent-to-Agent) protocol.

### 1.2 Goals

| Goal | Description |
|------|-------------|
| **Multi-Agent Orchestration** | Implement supervisor/hierarchical/swarm patterns using LangGraph v1.0.7 |
| **Universal Tool Integration** | Standardize all tool access through MCP servers |
| **Scalable Memory** | Three-tier memory architecture with PostgreSQL + pgvector |
| **Secure Execution** | Sandboxed code execution with Docker/Firecracker |
| **Observable Systems** | Full distributed tracing and audit logging |
| **Human-in-the-Loop** | Approval gates at critical SDLC decision points |

### 1.3 Current State vs Target State

```mermaid
graph LR
    subgraph Current State
        A[ReAct Engine] --> B[6 SDLC Agents]
        B --> C[Custom Tool Framework]
        C --> D[Qdrant Vector Store]
        D --> E[Sequential Orchestration]
    end
    
    subgraph Target State
        F[LangGraph StateGraph] --> G[8 SDLC Sub-Agents]
        G --> H[MCP Server Stack]
        H --> I[PostgreSQL + pgvector]
        I --> J[Supervisor/Swarm Patterns]
    end
    
    A -.->|Migration| F
    B -.->|Expansion| G
    C -.->|Standardization| H
    D -.->|Consolidation| I
    E -.->|Enhancement| J
```

---

## 2. Architecture Overview

### 2.1 High-Level Component Diagram

```mermaid
graph TB
    subgraph Client Layer
        CLI[CLI Interface]
        API[REST/WebSocket API]
        WEB[Web Dashboard]
    end
    
    subgraph Orchestration Layer
        SUPER[Supervisor Agent]
        HIER[Hierarchical Coordinators]
        SWARM[Swarm Controller]
    end
    
    subgraph Agent Layer
        REQ[Requirements Agent]
        SYS[System Design Agent]
        ARCH[Architecture Agent]
        CODE[Coding Agents - Pool]
        TEST[Testing Agent]
        CICD[CI/CD Agent]
        DEP[Deployment Agent]
        MON[Monitoring Agent]
    end
    
    subgraph Memory Layer
        EPIS[Episodic Memory - Tier 1]
        SEM[Semantic Memory - Tier 2]
        PROC[Procedural Memory - Tier 3]
    end
    
    subgraph Tool Layer
        MCP_FS[MCP: Filesystem]
        MCP_GIT[MCP: Git/GitHub]
        MCP_DB[MCP: PostgreSQL]
        MCP_SHELL[MCP: Shell]
        MCP_BROWSER[MCP: Puppeteer]
        MCP_K8S[MCP: Kubernetes]
        MCP_DOCKER[MCP: Docker]
    end
    
    subgraph Infrastructure Layer
        PG[(PostgreSQL + pgvector)]
        REDIS[(Redis)]
        SANDBOX[Docker/Firecracker Sandbox]
        OTEL[OpenTelemetry Collector]
    end
    
    CLI --> SUPER
    API --> SUPER
    WEB --> SUPER
    
    SUPER --> HIER
    HIER --> SWARM
    SWARM --> REQ & SYS & ARCH & CODE & TEST & CICD & DEP & MON
    
    REQ & SYS & ARCH & CODE & TEST & CICD & DEP & MON --> EPIS
    EPIS --> SEM
    SEM --> PROC
    
    REQ & SYS & ARCH & CODE & TEST & CICD & DEP & MON --> MCP_FS & MCP_GIT & MCP_DB & MCP_SHELL & MCP_BROWSER & MCP_K8S & MCP_DOCKER
    
    MCP_FS & MCP_SHELL --> SANDBOX
    EPIS & SEM & PROC --> PG
    SUPER --> REDIS
    OTEL --> PG
```

### 2.2 Data Flow Architecture

```mermaid
sequenceDiagram
    participant U as User
    participant S as Supervisor
    participant W as Worker Agent
    participant M as MCP Server
    participant DB as PostgreSQL
    participant SB as Sandbox
    
    U->>S: Submit Task
    S->>DB: Load State from Checkpoint
    S->>S: Route to Appropriate Worker
    
    loop Agent Execution
        S->>W: Delegate Subtask
        W->>DB: Query Semantic Memory
        W->>M: Request Tool Execution
        M->>SB: Execute in Sandbox
        SB-->>M: Return Result
        M-->>W: Tool Response
        W->>DB: Store Episodic Memory
        W-->>S: Return Subtask Result
    end
    
    S->>DB: Persist State Checkpoint
    S-->>U: Return Final Result
```

### 2.3 Key Design Principles

1. **State-Centric Design**: All agent state managed through LangGraph's TypedDict-based state graphs
2. **Tool Abstraction**: All tools accessed via MCP protocol for standardization and security
3. **Memory Hierarchy**: Three-tier memory enables both fast access and cross-project learning
4. **Sandboxed Execution**: Code execution isolated in containerized environments
5. **Observable by Default**: Every operation traced and auditable
6. **Human Gates**: Critical decisions require human approval

---

## 3. LangGraph Integration Design

### 3.1 Migration from ReAct Engine

The current implementation uses a custom [`ReActEngine`](../../src/agent/core/engine.py:64) class with manual iteration loops. This will be replaced by LangGraph's native state graph implementation.

**Current Implementation** (to be replaced):
- [`ReActEngine`](../../src/agent/core/engine.py:64) - Manual planning/execution/reflection loop
- [`AgentOrchestrator`](../../src/agent/core/orchestrator.py:59) - Sequential stage execution
- [`WorkflowStage`](../../src/agent/core/orchestrator.py:27) enum for SDLC phases

**Target Implementation**:
- `StateGraph` with compiled workflows
- Supervisor/Worker pattern for agent coordination
- PostgresSaver for state persistence

### 3.2 Supervisor Hierarchy Structure

```mermaid
graph TB
    subgraph Level 0 - Master Supervisor
        MS[SDLC Supervisor]
    end
    
    subgraph Level 1 - Phase Supervisors
        PS_REQ[Requirements Phase]
        PS_DEV[Development Phase]
        PS_OPS[Operations Phase]
    end
    
    subgraph Level 2 - Specialized Workers
        W_REQ[Requirements Agent]
        W_SYS[System Design Agent]
        W_ARCH[Architecture Agent]
        W_CODE1[Coding Agent 1]
        W_CODE2[Coding Agent 2]
        W_CODE3[Coding Agent N]
        W_TEST[Testing Agent]
        W_CICD[CI/CD Agent]
        W_DEP[Deployment Agent]
        W_MON[Monitoring Agent]
    end
    
    MS --> PS_REQ & PS_DEV & PS_OPS
    PS_REQ --> W_REQ & W_SYS
    PS_DEV --> W_ARCH & W_CODE1 & W_CODE2 & W_CODE3 & W_TEST
    PS_OPS --> W_CICD & W_DEP & W_MON
    
    W_CODE1 <-.-> W_TEST
    W_TEST <-.-> W_CODE1
```

### 3.3 State Graph Definition

```python
# src/agent/langgraph/state.py

from typing import TypedDict, Annotated, Literal, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres import PostgresSaver

class SDLCMessage(TypedDict):
    """Message structure for SDLC communication."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    agent_id: str | None
    timestamp: str
    metadata: dict

class SDLCState(TypedDict):
    """Main state schema for SDLC workflow."""
    # Conversation and messages
    messages: Annotated[Sequence[SDLCMessage], add_messages]
    
    # Project context
    project_id: str
    project_name: str
    project_path: str
    
    # Current phase tracking
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
    phase_status: Literal["pending", "in_progress", "blocked", "completed", "failed"]
    
    # Artifacts produced by agents
    artifacts: dict[str, dict]  # phase -> artifact_data
    
    # Human approval gates
    pending_approvals: list[dict]
    approved_items: list[str]
    
    # Error handling
    errors: list[dict]
    retry_count: int
    
    # Routing decisions
    next_agent: str | None
    routing_reason: str | None

# Supervisor routing function
def supervisor_router(state: SDLCState) -> Literal[
    "requirements_agent",
    "system_design_agent",
    "architecture_agent",
    "coding_pool",
    "testing_agent",
    "cicd_agent",
    "deployment_agent",
    "monitoring_agent",
    "human_approval",
    "end"
]:
    """Route to next agent based on state."""
    if state.get("pending_approvals"):
        return "human_approval"
    
    phase = state.get("current_phase")
    status = state.get("phase_status")
    
    if status == "completed":
        # Progress to next phase
        phase_order = [
            "requirements", "system_design", "architecture",
            "implementation", "testing", "ci_cd", 
            "deployment", "monitoring"
        ]
        current_idx = phase_order.index(phase)
        if current_idx < len(phase_order) - 1:
            next_phase = phase_order[current_idx + 1]
            return f"{next_phase}_agent"
        return "end"
    
    # Route to current phase agent
    agent_mapping = {
        "requirements": "requirements_agent",
        "system_design": "system_design_agent",
        "architecture": "architecture_agent",
        "implementation": "coding_pool",
        "testing": "testing_agent",
        "ci_cd": "cicd_agent",
        "deployment": "deployment_agent",
        "monitoring": "monitoring_agent"
    }
    return agent_mapping.get(phase, "end")
```

### 3.4 Checkpoint/Persistence Strategy

```python
# src/agent/langgraph/persistence.py

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

class SDLCCheckpointer:
    """Manages checkpoint persistence for SDLC workflows."""
    
    def __init__(self, connection_string: str):
        self.pool = ConnectionPool(
            conninfo=connection_string,
            min_size=5,
            max_size=20
        )
        self.checkpointer = PostgresSaver(self.pool)
    
    async def setup(self):
        """Initialize checkpoint tables."""
        async with self.pool.connection() as conn:
            await self.checkpointer.setup()
    
    def get_checkpointer(self) -> PostgresSaver:
        """Get checkpointer for graph compilation."""
        return self.checkpointer
    
    async def list_threads(self, project_id: str) -> list[dict]:
        """List all threads for a project."""
        async with self.pool.connection() as conn:
            result = await conn.execute(
                "SELECT thread_id, created_at, updated_at FROM checkpoints WHERE metadata->>'project_id' = $1",
                [project_id]
            )
            return [dict(row) for row in await result.fetchall()]
    
    async def resume_thread(self, thread_id: str) -> dict | None:
        """Resume execution from a checkpoint."""
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.checkpointer.aget(config)
        return state
```

### 3.5 Human-in-the-Loop Gates

```python
# src/agent/langgraph/approval.py

from langgraph.types import interrupt

APPROVAL_GATES = {
    "requirements": ["prd_approval", "user_story_approval"],
    "system_design": ["schema_approval", "api_spec_approval"],
    "architecture": ["tech_stack_approval", "security_review"],
    "implementation": ["code_review", "merge_approval"],
    "deployment": ["production_deployment_approval"],
}

async def human_approval_node(state: SDLCState) -> SDLCState:
    """Handle human approval gates."""
    pending = state.get("pending_approvals", [])
    
    if not pending:
        return state
    
    approval_request = pending[0]
    
    # Interrupt execution and wait for human input
    decision = interrupt({
        "type": "approval_request",
        "gate": approval_request["gate"],
        "phase": approval_request["phase"],
        "artifact": approval_request["artifact_id"],
        "summary": approval_request["summary"],
        "options": ["approve", "reject", "request_changes"]
    })
    
    # Process decision
    if decision["action"] == "approve":
        state["approved_items"].append(approval_request["artifact_id"])
        state["pending_approvals"] = pending[1:]  # Remove processed
    elif decision["action"] == "reject":
        state["errors"].append({
            "type": "approval_rejected",
            "gate": approval_request["gate"],
            "reason": decision.get("reason", "")
        })
        state["phase_status"] = "failed"
    else:  # request_changes
        state["phase_status"] = "blocked"
        state["messages"].append({
            "role": "user",
            "content": f"Changes requested: {decision.get('feedback', '')}",
            "agent_id": None,
            "timestamp": datetime.now().isoformat(),
            "metadata": {"change_request": True}
        })
    
    return state
```

### 3.6 Swarm Pattern for Code-Test-Fix Loops

```python
# src/agent/langgraph/swarm.py

from langgraph.prebuilt import create_swarm

def create_coding_swarm():
    """Create a swarm of coding and testing agents for iterative development."""
    
    coding_agent = create_agent(
        name="coding_agent",
        tools=[mcp_filesystem, mcp_git],
        system_prompt=CODING_SYSTEM_PROMPT
    )
    
    testing_agent = create_agent(
        name="testing_agent", 
        tools=[mcp_shell, mcp_filesystem],
        system_prompt=TESTING_SYSTEM_PROMPT
    )
    
    # Handoff definitions for peer-to-peer collaboration
    coding_agent.handoffs = [
        Handoff(
            target="testing_agent",
            condition="code_ready_for_testing",
            context_transfer=["file_paths", "change_summary"]
        )
    ]
    
    testing_agent.handoffs = [
        Handoff(
            target="coding_agent",
            condition="tests_failed",
            context_transfer=["failure_report", "suggested_fixes"]
        ),
        Handoff(
            target="supervisor",
            condition="tests_passed",
            context_transfer=["coverage_report", "test_results"]
        )
    ]
    
    return create_swarm(
        agents=[coding_agent, testing_agent],
        default_agent="coding_agent"
    )
```

---

## 4. MCP Integration Design

### 4.1 MCP Server Architecture

The Model Context Protocol (MCP) provides a standardized JSON-RPC 2.0 interface for tool integration. All current tools in [`src/agent/tools/`](../../src/agent/tools/) will be migrated to MCP servers.

```mermaid
graph TB
    subgraph Agent Process
        AGENT[LangGraph Agent]
        MCP_CLIENT[MCP Client]
    end
    
    subgraph MCP Servers - stdio transport
        FS[mcp-server-filesystem]
        GIT[mcp-server-git]
        GITHUB[mcp-server-github]
        SHELL[mcp-server-shell]
        MEM[mcp-server-memory]
    end
    
    subgraph MCP Servers - HTTP transport
        PG[mcp-server-postgres]
        DOCKER[mcp-server-docker]
        K8S[mcp-server-kubernetes]
        BROWSER[mcp-server-puppeteer]
        FETCH[mcp-server-fetch]
    end
    
    AGENT --> MCP_CLIENT
    MCP_CLIENT -->|stdio| FS & GIT & GITHUB & SHELL & MEM
    MCP_CLIENT -->|HTTP/SSE| PG & DOCKER & K8S & BROWSER & FETCH
```

### 4.2 MCP Server Mapping per SDLC Phase

| SDLC Phase | Primary MCP Servers | Secondary MCP Servers |
|------------|---------------------|----------------------|
| **Requirements** | filesystem, memory, fetch | github |
| **System Design** | filesystem, postgres, memory | fetch |
| **Architecture** | filesystem, git, github | docker |
| **Implementation** | filesystem, git, shell | docker, postgres |
| **Testing** | filesystem, shell, puppeteer | postgres, docker |
| **CI/CD** | git, github, shell | docker, kubernetes |
| **Deployment** | kubernetes, docker, shell | git, github |
| **Monitoring** | postgres, fetch, shell | kubernetes |

### 4.3 Transport Selection Strategy

```python
# src/agent/mcp/config.py

from enum import Enum
from pydantic import BaseModel

class MCPTransport(str, Enum):
    STDIO = "stdio"  # Local process communication
    HTTP_SSE = "http+sse"  # Remote server communication

class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""
    name: str
    transport: MCPTransport
    command: str | None = None  # For stdio
    url: str | None = None  # For HTTP
    args: list[str] = []
    env: dict[str, str] = {}
    capabilities: list[str] = []  # tools, prompts, resources

# Server configurations
MCP_SERVERS = {
    "filesystem": MCPServerConfig(
        name="filesystem",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-filesystem", "/workspace"],
        capabilities=["tools", "resources"]
    ),
    "git": MCPServerConfig(
        name="git",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-git"],
        capabilities=["tools"]
    ),
    "github": MCPServerConfig(
        name="github",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-github"],
        env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        capabilities=["tools", "resources"]
    ),
    "postgres": MCPServerConfig(
        name="postgres",
        transport=MCPTransport.HTTP_SSE,
        url="http://mcp-postgres:8080",
        capabilities=["tools", "resources"]
    ),
    "shell": MCPServerConfig(
        name="shell",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-shell"],
        capabilities=["tools"]
    ),
    "docker": MCPServerConfig(
        name="docker",
        transport=MCPTransport.HTTP_SSE,
        url="http://mcp-docker:8080",
        capabilities=["tools"]
    ),
    "kubernetes": MCPServerConfig(
        name="kubernetes",
        transport=MCPTransport.HTTP_SSE,
        url="http://mcp-kubernetes:8080",
        capabilities=["tools", "resources"]
    ),
    "puppeteer": MCPServerConfig(
        name="puppeteer",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-puppeteer"],
        capabilities=["tools"]
    ),
    "memory": MCPServerConfig(
        name="memory",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-memory"],
        capabilities=["tools", "resources"]
    ),
    "fetch": MCPServerConfig(
        name="fetch",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@anthropic/mcp-server-fetch"],
        capabilities=["tools"]
    ),
}
```

### 4.4 Tool Loading Strategy

```python
# src/agent/mcp/loader.py

from mcp import ClientSession, StdioServerParameters, HttpServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from langchain_core.tools import BaseTool
from langchain_mcp_adapters import load_mcp_tools

class MCPToolLoader:
    """Dynamically loads tools from MCP servers."""
    
    def __init__(self, server_configs: dict[str, MCPServerConfig]):
        self.configs = server_configs
        self.sessions: dict[str, ClientSession] = {}
        self.tools: dict[str, list[BaseTool]] = {}
    
    async def connect_server(self, server_name: str) -> ClientSession:
        """Connect to an MCP server."""
        config = self.configs[server_name]
        
        if config.transport == MCPTransport.STDIO:
            params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env
            )
            read, write = await stdio_client(params)
        else:
            params = HttpServerParameters(url=config.url)
            read, write = await sse_client(params)
        
        session = ClientSession(read, write)
        await session.initialize()
        self.sessions[server_name] = session
        return session
    
    async def load_tools_for_phase(self, phase: str) -> list[BaseTool]:
        """Load all tools needed for an SDLC phase."""
        server_names = PHASE_SERVER_MAPPING.get(phase, [])
        tools = []
        
        for server_name in server_names:
            if server_name not in self.sessions:
                await self.connect_server(server_name)
            
            session = self.sessions[server_name]
            server_tools = await load_mcp_tools(session)
            tools.extend(server_tools)
            self.tools[server_name] = server_tools
        
        return tools
    
    async def close_all(self):
        """Close all MCP connections."""
        for session in self.sessions.values():
            await session.close()
        self.sessions.clear()
```

### 4.5 Migration from Current Tool Framework

**Current Tool Structure** (to be migrated):
- [`BaseTool`](../../src/agent/tools/base.py:48) - Abstract tool interface
- [`ToolRegistry`](../../src/agent/tools/base.py:189) - Tool registration
- [`filesystem/`](../../src/agent/tools/filesystem/) - File operations
- [`git/`](../../src/agent/tools/git/) - Git operations  
- [`shell/`](../../src/agent/tools/shell/) - Shell execution

**Migration Path**:

| Current Tool | Target MCP Server | Migration Notes |
|--------------|-------------------|-----------------|
| `ReadFileTool` | `@anthropic/mcp-server-filesystem` | Direct mapping |
| `WriteFileTool` | `@anthropic/mcp-server-filesystem` | Direct mapping |
| `FileSearchTool` | `@anthropic/mcp-server-filesystem` | Add glob support |
| `GitOperationsTool` | `@anthropic/mcp-server-git` | Split into atomic ops |
| `ShellExecutor` | `@anthropic/mcp-server-shell` | Add sandboxing |
| Custom Calculator | Remove | Not needed for SDLC |

---

## 5. A2A Protocol Integration

### 5.1 A2A Overview

The Agent-to-Agent (A2A) protocol enables standardized communication between agents, supporting:
- Agent discovery via Agent Cards
- Task lifecycle management
- Streaming responses
- Push notifications

### 5.2 Agent Card Specifications

```python
# src/agent/a2a/cards.py

from pydantic import BaseModel
from typing import Literal

class AgentCapabilitySpec(BaseModel):
    """Specification of agent capabilities for A2A."""
    name: str
    description: str
    input_schema: dict  # JSON Schema
    output_schema: dict  # JSON Schema

class AgentCard(BaseModel):
    """A2A Agent Card definition."""
    agent_id: str
    name: str
    description: str
    version: str
    protocol_version: str = "1.0"
    
    # Capabilities
    capabilities: list[AgentCapabilitySpec]
    supported_phases: list[str]
    
    # Communication
    endpoint: str | None = None  # For remote agents
    transport: Literal["local", "http", "grpc"] = "local"
    
    # Authentication
    auth_required: bool = False
    auth_methods: list[str] = []
    
    # Metadata
    tags: list[str] = []
    documentation_url: str | None = None

# Agent Cards for SDLC Agents
REQUIREMENTS_AGENT_CARD = AgentCard(
    agent_id="requirements-agent-v2",
    name="Requirements Analysis Agent",
    description="Analyzes project requirements, generates PRDs, user stories, and acceptance criteria",
    version="2.0.0",
    capabilities=[
        AgentCapabilitySpec(
            name="analyze_requirements",
            description="Analyze raw requirements and generate structured output",
            input_schema={
                "type": "object",
                "properties": {
                    "raw_requirements": {"type": "string"},
                    "project_context": {"type": "object"}
                },
                "required": ["raw_requirements"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "prd": {"type": "object"},
                    "user_stories": {"type": "array"},
                    "acceptance_criteria": {"type": "array"},
                    "priorities": {"type": "object"}
                }
            }
        ),
        AgentCapabilitySpec(
            name="generate_user_stories",
            description="Generate user stories from requirements",
            input_schema={
                "type": "object",
                "properties": {
                    "requirements": {"type": "array"},
                    "stakeholders": {"type": "array"}
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "stories": {"type": "array"},
                    "epic_mapping": {"type": "object"}
                }
            }
        )
    ],
    supported_phases=["requirements"],
    tags=["requirements", "prd", "user-stories"]
)
```

### 5.3 Task Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> submitted: Create Task
    
    submitted --> working: Agent Accepts
    submitted --> rejected: Agent Rejects
    
    working --> streaming: Begin Output
    working --> input_required: Need User Input
    working --> completed: Task Done
    working --> failed: Error Occurred
    
    streaming --> working: Continue Processing
    streaming --> completed: Output Complete
    
    input_required --> working: Input Received
    input_required --> cancelled: Timeout/Cancel
    
    completed --> [*]
    failed --> [*]
    rejected --> [*]
    cancelled --> [*]
```

```python
# src/agent/a2a/task.py

from enum import Enum
from pydantic import BaseModel
from datetime import datetime

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    STREAMING = "streaming"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class A2ATask(BaseModel):
    """A2A Task representation."""
    task_id: str
    source_agent_id: str
    target_agent_id: str
    capability: str
    
    state: TaskState = TaskState.SUBMITTED
    
    # Input/Output
    input_data: dict
    output_data: dict | None = None
    
    # Streaming
    stream_buffer: list[dict] = []
    
    # Lifecycle timestamps
    created_at: datetime
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Error handling
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Metadata
    metadata: dict = {}

class A2ATaskManager:
    """Manages A2A task lifecycle."""
    
    def __init__(self, db_pool):
        self.pool = db_pool
        self.tasks: dict[str, A2ATask] = {}
    
    async def create_task(
        self,
        source_agent: str,
        target_agent: str,
        capability: str,
        input_data: dict
    ) -> A2ATask:
        """Create a new A2A task."""
        task = A2ATask(
            task_id=str(uuid.uuid4()),
            source_agent_id=source_agent,
            target_agent_id=target_agent,
            capability=capability,
            input_data=input_data,
            created_at=datetime.now()
        )
        self.tasks[task.task_id] = task
        await self._persist_task(task)
        return task
    
    async def transition_state(
        self,
        task_id: str,
        new_state: TaskState,
        data: dict | None = None
    ) -> A2ATask:
        """Transition task to new state with validation."""
        task = self.tasks[task_id]
        
        # Validate state transition
        valid_transitions = {
            TaskState.SUBMITTED: [TaskState.WORKING, TaskState.REJECTED],
            TaskState.WORKING: [
                TaskState.STREAMING, 
                TaskState.INPUT_REQUIRED,
                TaskState.COMPLETED, 
                TaskState.FAILED
            ],
            TaskState.STREAMING: [TaskState.WORKING, TaskState.COMPLETED],
            TaskState.INPUT_REQUIRED: [TaskState.WORKING, TaskState.CANCELLED],
        }
        
        if new_state not in valid_transitions.get(task.state, []):
            raise ValueError(f"Invalid transition: {task.state} -> {new_state}")
        
        task.state = new_state
        
        if new_state == TaskState.WORKING:
            task.accepted_at = datetime.now()
        elif new_state == TaskState.COMPLETED:
            task.completed_at = datetime.now()
            task.output_data = data
        elif new_state == TaskState.FAILED:
            task.error = data.get("error") if data else "Unknown error"
        
        await self._persist_task(task)
        return task
```

### 5.4 LangGraph-A2A Bridging

```python
# src/agent/a2a/bridge.py

from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres import PostgresSaver

class LangGraphA2ABridge:
    """Bridge between LangGraph execution and A2A protocol."""
    
    def __init__(
        self,
        task_manager: A2ATaskManager,
        agent_registry: dict[str, AgentCard]
    ):
        self.task_manager = task_manager
        self.agent_registry = agent_registry
    
    async def execute_a2a_task(
        self,
        task: A2ATask,
        graph: StateGraph,
        checkpointer: PostgresSaver
    ) -> dict:
        """Execute an A2A task using LangGraph."""
        
        # Convert A2A input to LangGraph state
        initial_state = self._a2a_to_langgraph_state(task)
        
        # Compile graph with checkpointer
        app = graph.compile(checkpointer=checkpointer)
        
        # Create thread config
        config = {
            "configurable": {
                "thread_id": task.task_id,
                "checkpoint_ns": task.target_agent_id
            }
        }
        
        # Execute with streaming
        await self.task_manager.transition_state(
            task.task_id, TaskState.WORKING
        )
        
        final_state = None
        async for event in app.astream(initial_state, config):
            # Stream updates
            await self.task_manager.transition_state(
                task.task_id, 
                TaskState.STREAMING,
                {"event": event}
            )
            
            # Check for interrupts (human-in-the-loop)
            if self._is_interrupt(event):
                await self.task_manager.transition_state(
                    task.task_id,
                    TaskState.INPUT_REQUIRED,
                    {"interrupt": event}
                )
                # Wait for input...
            
            final_state = event
        
        # Complete task
        output = self._langgraph_state_to_a2a_output(final_state)
        await self.task_manager.transition_state(
            task.task_id,
            TaskState.COMPLETED,
            output
        )
        
        return output
    
    def _a2a_to_langgraph_state(self, task: A2ATask) -> SDLCState:
        """Convert A2A task input to LangGraph state."""
        return SDLCState(
            messages=[{
                "role": "user",
                "content": json.dumps(task.input_data),
                "agent_id": task.source_agent_id,
                "timestamp": task.created_at.isoformat(),
                "metadata": {"a2a_task_id": task.task_id}
            }],
            project_id=task.input_data.get("project_id", ""),
            project_name=task.input_data.get("project_name", ""),
            project_path=task.input_data.get("project_path", ""),
            current_phase=task.input_data.get("phase", "requirements"),
            phase_status="in_progress",
            artifacts={},
            pending_approvals=[],
            approved_items=[],
            errors=[],
            retry_count=0,
            next_agent=None,
            routing_reason=None
        )
```

---

## 6. Sub-Agent Specifications

### 6.1 Agent Overview Matrix

| # | Agent | Input Contract | Output Contract | Primary Tools | Approval Gate |
|---|-------|---------------|-----------------|---------------|---------------|
| 1 | Requirements Agent | Raw requirements, stakeholder info | PRD, User Stories, Acceptance Criteria | filesystem, memory, fetch | PRD Approval |
| 2 | System Design Agent | PRD, User Stories | Database Schema, API Specs, Architecture Doc | filesystem, postgres, memory | Schema Approval |
| 3 | Architecture Agent | System Design Docs | Tech Stack, Project Structure, Scaffolding | filesystem, git, github | Tech Stack Approval |
| 4 | Coding Agents (Pool) | Architecture, Specs | Source Code Files | filesystem, git, shell | Code Review |
| 5 | Testing Agent | Source Code, Specs | Test Files, Coverage Report | filesystem, shell, puppeteer | Coverage Threshold |
| 6 | CI/CD Agent | Project Structure | Pipeline Config, Build Scripts | git, github, shell | Pipeline Approval |
| 7 | Deployment Agent | CI/CD Config | K8s Manifests, Terraform, Docker | kubernetes, docker, shell | Production Deploy |
| 8 | Monitoring Agent | Deployment Config | Dashboards, Alerts, Runbooks | postgres, fetch, kubernetes | Alert Config |

### 6.2 Requirements Agent Specification

**Migration from**: [`RequirementsAgent`](../../src/agent/agents/requirements_agent.py:9)

```python
# src/agent/agents/v2/requirements_agent.py

class RequirementsAgentV2:
    """Requirements Agent for PRD generation and user story creation."""
    
    agent_id = "requirements-agent-v2"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "raw_requirements": {
                "type": "string",
                "description": "Raw requirements text from stakeholder"
            },
            "project_context": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "existing_systems": {"type": "array"},
                    "constraints": {"type": "array"}
                }
            },
            "stakeholders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "priorities": {"type": "array"}
                    }
                }
            }
        },
        "required": ["raw_requirements"]
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "prd": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "overview": {"type": "string"},
                    "goals": {"type": "array"},
                    "non_goals": {"type": "array"},
                    "success_metrics": {"type": "array"}
                }
            },
            "user_stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "story": {"type": "string"},
                        "priority": {"enum": ["must", "should", "could", "wont"]},
                        "acceptance_criteria": {"type": "array"}
                    }
                }
            },
            "nfr": {
                "type": "object",
                "properties": {
                    "performance": {"type": "array"},
                    "security": {"type": "array"},
                    "scalability": {"type": "array"}
                }
            }
        },
        "required": ["prd", "user_stories"]
    }
    
    TOOL_ASSIGNMENTS = ["filesystem", "memory", "fetch"]
    APPROVAL_GATES = ["prd_approval", "user_story_approval"]
    
    SYSTEM_PROMPT = """You are a Requirements Analysis Agent specialized in software requirements engineering.

## Expertise
- Stakeholder analysis and requirements elicitation
- PRD (Product Requirements Document) generation
- User story creation following INVEST principles
- Acceptance criteria in Given-When-Then format
- MoSCoW prioritization

## Process
1. Analyze raw requirements and context
2. Identify stakeholders and their needs
3. Generate structured PRD
4. Create user stories with acceptance criteria
5. Classify by priority (Must/Should/Could/Wont)
6. Identify non-functional requirements

## Output Format
Always output structured JSON matching the output contract schema.
"""
```

### 6.3 System Design Agent Specification

**New Agent** (not in current codebase)

```python
class SystemDesignAgent:
    """System Design Agent for database schemas and API specifications."""
    
    agent_id = "system-design-agent-v1"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "prd": {"type": "object"},
            "user_stories": {"type": "array"},
            "constraints": {
                "type": "object",
                "properties": {
                    "database": {"type": "string"},
                    "api_style": {"enum": ["rest", "graphql", "grpc"]},
                    "scale_requirements": {"type": "object"}
                }
            }
        },
        "required": ["prd", "user_stories"]
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "database_schema": {
                "type": "object",
                "properties": {
                    "entities": {"type": "array"},
                    "relationships": {"type": "array"},
                    "indexes": {"type": "array"},
                    "migrations": {"type": "array"}
                }
            },
            "api_specification": {
                "type": "object",
                "properties": {
                    "openapi_version": {"type": "string"},
                    "endpoints": {"type": "array"},
                    "schemas": {"type": "object"}
                }
            },
            "data_flow": {
                "type": "object",
                "properties": {
                    "diagrams": {"type": "array"},
                    "integrations": {"type": "array"}
                }
            }
        }
    }
    
    TOOL_ASSIGNMENTS = ["filesystem", "postgres", "memory"]
    APPROVAL_GATES = ["schema_approval", "api_spec_approval"]
```

### 6.4 Architecture Agent Specification

**Migration from**: [`ArchitectureAgent`](../../src/agent/agents/architecture_agent.py)

```python
class ArchitectureAgentV2:
    """Architecture Agent for tech stack decisions and project scaffolding."""
    
    agent_id = "architecture-agent-v2"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "system_design": {"type": "object"},
            "constraints": {
                "type": "object",
                "properties": {
                    "languages": {"type": "array"},
                    "frameworks": {"type": "array"},
                    "cloud_provider": {"type": "string"},
                    "budget_tier": {"enum": ["startup", "growth", "enterprise"]}
                }
            }
        }
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "tech_stack": {
                "type": "object",
                "properties": {
                    "frontend": {"type": "object"},
                    "backend": {"type": "object"},
                    "database": {"type": "object"},
                    "infrastructure": {"type": "object"},
                    "rationale": {"type": "array"}
                }
            },
            "project_structure": {
                "type": "object",
                "properties": {
                    "directories": {"type": "array"},
                    "config_files": {"type": "array"},
                    "scaffolding_commands": {"type": "array"}
                }
            },
            "architecture_diagram": {"type": "string"}  # Mermaid format
        }
    }
    
    TOOL_ASSIGNMENTS = ["filesystem", "git", "github", "docker"]
    APPROVAL_GATES = ["tech_stack_approval", "security_review"]
```

### 6.5 Coding Agents Pool Specification

**Migration from**: [`ImplementationAgent`](../../src/agent/agents/implementation_agent.py)

```python
class CodingAgentPool:
    """Pool of coding agents for parallel file-level code generation."""
    
    agent_id_prefix = "coding-agent-"
    pool_size = 5  # Configurable
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "file_spec": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "purpose": {"type": "string"},
                    "dependencies": {"type": "array"},
                    "interfaces": {"type": "array"}
                }
            },
            "context": {
                "type": "object",
                "properties": {
                    "architecture": {"type": "object"},
                    "coding_standards": {"type": "object"},
                    "existing_code": {"type": "array"}
                }
            }
        }
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"},
            "imports": {"type": "array"},
            "exports": {"type": "array"},
            "test_hints": {"type": "array"}
        }
    }
    
    TOOL_ASSIGNMENTS = ["filesystem", "git", "shell"]
    
    # Swarm handoffs
    HANDOFFS = [
        {
            "target": "testing-agent",
            "condition": "file_ready_for_testing",
            "context_transfer": ["file_path", "exports", "test_hints"]
        }
    ]
```

### 6.6 Testing Agent Specification

**Migration from**: [`TestingAgent`](../../src/agent/agents/testing_agent.py:9)

```python
class TestingAgentV2:
    """Testing Agent for comprehensive test generation."""
    
    agent_id = "testing-agent-v2"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "source_files": {"type": "array"},
            "test_requirements": {
                "type": "object",
                "properties": {
                    "coverage_target": {"type": "number"},
                    "test_types": {"type": "array"},  # unit, integration, e2e
                    "frameworks": {"type": "object"}
                }
            }
        }
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "test_files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "test_count": {"type": "number"}
                    }
                }
            },
            "coverage_report": {
                "type": "object",
                "properties": {
                    "overall": {"type": "number"},
                    "by_file": {"type": "object"},
                    "uncovered_lines": {"type": "array"}
                }
            }
        }
    }
    
    TOOL_ASSIGNMENTS = ["filesystem", "shell", "puppeteer"]
    
    # Swarm handoffs
    HANDOFFS = [
        {
            "target": "coding-agent-pool",
            "condition": "tests_failed",
            "context_transfer": ["failure_report", "suggested_fixes"]
        },
        {
            "target": "supervisor",
            "condition": "tests_passed_and_coverage_met",
            "context_transfer": ["coverage_report"]
        }
    ]
```

### 6.7 CI/CD Agent Specification

**New Agent**

```python
class CICDAgent:
    """CI/CD Agent for pipeline configuration and build automation."""
    
    agent_id = "cicd-agent-v1"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "project_structure": {"type": "object"},
            "ci_platform": {"enum": ["github_actions", "gitlab_ci", "jenkins", "circleci"]},
            "deployment_targets": {"type": "array"}
        }
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "pipeline_config": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                    "stages": {"type": "array"}
                }
            },
            "build_scripts": {"type": "array"},
            "environment_configs": {"type": "array"}
        }
    }
    
    TOOL_ASSIGNMENTS = ["git", "github", "shell", "docker"]
    APPROVAL_GATES = ["pipeline_approval"]
```

### 6.8 Deployment Agent Specification

**Migration from**: [`DeploymentAgent`](../../src/agent/agents/deployment_agent.py:9)

```python
class DeploymentAgentV2:
    """Deployment Agent for infrastructure and container orchestration."""
    
    agent_id = "deployment-agent-v2"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "ci_cd_config": {"type": "object"},
            "infrastructure_requirements": {
                "type": "object",
                "properties": {
                    "cloud_provider": {"type": "string"},
                    "compute": {"type": "object"},
                    "networking": {"type": "object"},
                    "storage": {"type": "object"}
                }
            },
            "deployment_strategy": {"enum": ["rolling", "blue_green", "canary"]}
        }
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "kubernetes_manifests": {"type": "array"},
            "terraform_modules": {"type": "array"},
            "docker_configs": {"type": "array"},
            "deployment_runbook": {"type": "object"}
        }
    }
    
    TOOL_ASSIGNMENTS = ["kubernetes", "docker", "shell", "git"]
    APPROVAL_GATES = ["production_deployment_approval"]
```

### 6.9 Monitoring Agent Specification

**Migration from**: [`OperationsAgent`](../../src/agent/agents/operations_agent.py)

```python
class MonitoringAgent:
    """Monitoring Agent for observability setup and alerting."""
    
    agent_id = "monitoring-agent-v1"
    
    INPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "deployment_config": {"type": "object"},
            "sla_requirements": {
                "type": "object",
                "properties": {
                    "availability": {"type": "number"},
                    "latency_p99": {"type": "number"},
                    "error_rate": {"type": "number"}
                }
            },
            "monitoring_stack": {"enum": ["prometheus_grafana", "datadog", "newrelic"]}
        }
    }
    
    OUTPUT_CONTRACT = {
        "type": "object",
        "properties": {
            "dashboards": {"type": "array"},
            "alert_rules": {"type": "array"},
            "runbooks": {"type": "array"},
            "slo_definitions": {"type": "array"}
        }
    }
    
    TOOL_ASSIGNMENTS = ["postgres", "fetch", "kubernetes", "filesystem"]
    APPROVAL_GATES = ["alert_config_approval"]
```

---

## 7. Memory Architecture

### 7.1 Three-Tier Memory Overview

```mermaid
graph TB
    subgraph Tier 1 - Episodic Memory
        E1[Per-Task Conversation History]
        E2[Agent Execution Traces]
        E3[Tool Call Results]
    end
    
    subgraph Tier 2 - Semantic Memory
        S1[Project Knowledge Base]
        S2[Code Embeddings]
        S3[Document Embeddings]
    end
    
    subgraph Tier 3 - Procedural Memory
        P1[Cross-Project Patterns]
        P2[Learned Solutions]
        P3[Error Recovery Strategies]
    end
    
    subgraph Storage Backend
        PG[(PostgreSQL + pgvector)]
    end
    
    E1 & E2 & E3 --> PG
    S1 & S2 & S3 --> PG
    P1 & P2 & P3 --> PG
    
    E1 -.->|Summarization| S1
    S1 -.->|Pattern Extraction| P1
```

### 7.2 Tier 1: Episodic Memory (Per-Task)

**Migration from**: [`EpisodicMemory`](../../src/agent/memory/episodic.py:26)

```python
# src/agent/memory/v2/episodic.py

from langgraph.checkpoint.postgres import PostgresSaver

class EpisodicMemoryV2:
    """Per-task episodic memory using PostgresSaver."""
    
    def __init__(self, connection_pool):
        self.saver = PostgresSaver(connection_pool)
        
    async def setup(self):
        """Create episodic memory tables."""
        await self.saver.setup()
        
        # Additional indexes for efficient retrieval
        async with self.pool.connection() as conn:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread 
                ON checkpoints (thread_id, checkpoint_ts DESC);
                
                CREATE INDEX IF NOT EXISTS idx_checkpoints_metadata 
                ON checkpoints USING gin (metadata jsonb_path_ops);
            """)
    
    async def store_episode(
        self,
        thread_id: str,
        episode: dict,
        metadata: dict
    ):
        """Store a single episode in the checkpoint."""
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get current state
        current = await self.saver.aget(config)
        
        # Append episode
        if current:
            current["messages"].append(episode)
        else:
            current = {"messages": [episode]}
        
        # Save checkpoint
        await self.saver.aput(
            config,
            current,
            metadata=metadata
        )
    
    async def get_conversation_history(
        self,
        thread_id: str,
        limit: int = 100
    ) -> list[dict]:
        """Retrieve conversation history for a thread."""
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.saver.aget(config)
        
        if not state:
            return []
        
        messages = state.get("messages", [])
        return messages[-limit:]
```

### 7.3 Tier 2: Semantic Memory (Per-Project)

**Migration from**: [`VectorStore`](../../src/agent/memory/vector_store.py:34)

```python
# src/agent/memory/v2/semantic.py

from pgvector.psycopg import register_vector
import numpy as np

class SemanticMemoryV2:
    """Per-project semantic memory using PostgreSQL + pgvector."""
    
    EMBEDDING_DIM = 1536  # OpenAI ada-002 dimension
    
    def __init__(self, connection_pool, embedding_client):
        self.pool = connection_pool
        self.embedder = embedding_client
    
    async def setup(self):
        """Create semantic memory tables with pgvector."""
        async with self.pool.connection() as conn:
            # Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create semantic memory table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector({self.EMBEDDING_DIM}),
                    content_type TEXT NOT NULL,  -- 'code', 'doc', 'requirement', etc.
                    file_path TEXT,
                    chunk_index INT,
                    metadata JSONB DEFAULT '{{}}',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE INDEX IF NOT EXISTS idx_semantic_project 
                ON semantic_memory (project_id);
                
                CREATE INDEX IF NOT EXISTS idx_semantic_embedding 
                ON semantic_memory USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
            await register_vector(conn)
    
    async def store_document(
        self,
        project_id: str,
        content: str,
        content_type: str,
        file_path: str | None = None,
        metadata: dict | None = None
    ):
        """Store a document with its embedding."""
        # Generate embedding
        embedding = await self.embedder.embed_text(content)
        
        async with self.pool.connection() as conn:
            await conn.execute("""
                INSERT INTO semantic_memory 
                (project_id, content, embedding, content_type, file_path, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, [
                project_id,
                content,
                np.array(embedding),
                content_type,
                file_path,
                metadata or {}
            ])
    
    async def semantic_search(
        self,
        project_id: str,
        query: str,
        content_types: list[str] | None = None,
        limit: int = 10
    ) -> list[dict]:
        """Search for semantically similar content."""
        # Generate query embedding
        query_embedding = await self.embedder.embed_text(query)
        
        # Build query
        type_filter = ""
        params = [project_id, np.array(query_embedding), limit]
        
        if content_types:
            type_filter = "AND content_type = ANY($4)"
            params.append(content_types)
        
        async with self.pool.connection() as conn:
            results = await conn.execute(f"""
                SELECT 
                    id, content, content_type, file_path, metadata,
                    1 - (embedding <=> $2) as similarity
                FROM semantic_memory
                WHERE project_id = $1 {type_filter}
                ORDER BY embedding <=> $2
                LIMIT $3
            """, params)
            
            return [dict(row) for row in await results.fetchall()]
```

### 7.4 Tier 3: Procedural Memory (Cross-Project)

**Migration from**: [`ProceduralMemory`](../../src/agent/memory/procedural.py:53)

```python
# src/agent/memory/v2/procedural.py

class ProceduralMemoryV2:
    """Cross-project procedural memory for learned patterns."""
    
    def __init__(self, connection_pool, embedding_client):
        self.pool = connection_pool
        self.embedder = embedding_client
    
    async def setup(self):
        """Create procedural memory tables."""
        async with self.pool.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS procedural_patterns (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    pattern_type TEXT NOT NULL,
                    context_embedding vector(1536),
                    context_text TEXT NOT NULL,
                    solution_text TEXT NOT NULL,
                    success_count INT DEFAULT 1,
                    failure_count INT DEFAULT 0,
                    confidence FLOAT GENERATED ALWAYS AS (
                        CASE WHEN success_count + failure_count = 0 THEN 0.5
                        ELSE (success_count::float / (success_count + failure_count)) *
                             LEAST(1.0, LN(success_count + failure_count + 1) / 3)
                        END
                    ) STORED,
                    source_projects TEXT[],
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    last_used_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE INDEX IF NOT EXISTS idx_procedural_type 
                ON procedural_patterns (pattern_type);
                
                CREATE INDEX IF NOT EXISTS idx_procedural_confidence 
                ON procedural_patterns (confidence DESC);
                
                CREATE INDEX IF NOT EXISTS idx_procedural_context 
                ON procedural_patterns USING ivfflat (context_embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
    
    async def learn_pattern(
        self,
        pattern_type: str,
        context: str,
        solution: str,
        source_project: str,
        metadata: dict | None = None
    ):
        """Learn a new pattern from experience."""
        context_embedding = await self.embedder.embed_text(context)
        
        async with self.pool.connection() as conn:
            # Check for similar existing pattern
            similar = await conn.execute("""
                SELECT id, context_text, solution_text, success_count
                FROM procedural_patterns
                WHERE pattern_type = $1
                AND 1 - (context_embedding <=> $2) > 0.9
                LIMIT 1
            """, [pattern_type, np.array(context_embedding)])
            
            row = await similar.fetchone()
            
            if row:
                # Update existing pattern
                await conn.execute("""
                    UPDATE procedural_patterns
                    SET success_count = success_count + 1,
                        last_used_at = now(),
                        source_projects = array_append(
                            array_remove(source_projects, $2), $2
                        )
                    WHERE id = $1
                """, [row['id'], source_project])
            else:
                # Insert new pattern
                await conn.execute("""
                    INSERT INTO procedural_patterns
                    (pattern_type, context_embedding, context_text, 
                     solution_text, source_projects, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, [
                    pattern_type,
                    np.array(context_embedding),
                    context,
                    solution,
                    [source_project],
                    metadata or {}
                ])
    
    async def find_applicable_patterns(
        self,
        context: str,
        pattern_type: str | None = None,
        min_confidence: float = 0.6,
        limit: int = 5
    ) -> list[dict]:
        """Find patterns applicable to the current context."""
        context_embedding = await self.embedder.embed_text(context)
        
        type_filter = ""
        params = [np.array(context_embedding), min_confidence, limit]
        
        if pattern_type:
            type_filter = "AND pattern_type = $4"
            params.append(pattern_type)
        
        async with self.pool.connection() as conn:
            results = await conn.execute(f"""
                SELECT 
                    id, pattern_type, context_text, solution_text,
                    success_count, failure_count, confidence,
                    1 - (context_embedding <=> $1) as similarity
                FROM procedural_patterns
                WHERE confidence >= $2 {type_filter}
                ORDER BY confidence DESC, context_embedding <=> $1
                LIMIT $3
            """, params)
            
            return [dict(row) for row in await results.fetchall()]
```

### 7.5 State Schema (SDLCState TypedDict)

See [Section 3.3](#33-state-graph-definition) for the complete SDLCState TypedDict definition.

### 7.6 Cross-Agent Artifact Communication

```python
# src/agent/memory/v2/artifacts.py

class ArtifactStore:
    """Store and retrieve artifacts produced by agents."""
    
    def __init__(self, connection_pool, blob_storage):
        self.pool = connection_pool
        self.blob = blob_storage  # S3, GCS, or local filesystem
    
    async def setup(self):
        """Create artifact tables."""
        async with self.pool.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size_bytes BIGINT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    superseded_by UUID REFERENCES artifacts(id),
                    
                    CONSTRAINT unique_artifact_version 
                    UNIQUE (project_id, phase, name, content_hash)
                );
                
                CREATE INDEX IF NOT EXISTS idx_artifacts_project_phase 
                ON artifacts (project_id, phase);
                
                CREATE INDEX IF NOT EXISTS idx_artifacts_thread 
                ON artifacts (thread_id);
            """)
    
    async def store_artifact(
        self,
        project_id: str,
        thread_id: str,
        phase: str,
        agent_id: str,
        artifact_type: str,
        name: str,
        content: bytes | str,
        metadata: dict | None = None
    ) -> str:
        """Store an artifact and return its ID."""
        import hashlib
        
        # Calculate content hash
        if isinstance(content, str):
            content = content.encode('utf-8')
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Store in blob storage
        storage_path = f"{project_id}/{phase}/{name}_{content_hash[:8]}"
        await self.blob.put(storage_path, content)
        
        async with self.pool.connection() as conn:
            # Check for existing version
            existing = await conn.execute("""
                SELECT id FROM artifacts
                WHERE project_id = $1 AND phase = $2 AND name = $3
                AND superseded_by IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            """, [project_id, phase, name])
            
            existing_row = await existing.fetchone()
            
            # Insert new artifact
            result = await conn.execute("""
                INSERT INTO artifacts
                (project_id, thread_id, phase, agent_id, artifact_type,
                 name, storage_path, content_hash, size_bytes, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """, [
                project_id, thread_id, phase, agent_id, artifact_type,
                name, storage_path, content_hash, len(content), metadata or {}
            ])
            
            new_id = (await result.fetchone())['id']
            
            # Mark previous version as superseded
            if existing_row:
                await conn.execute("""
                    UPDATE artifacts SET superseded_by = $1
                    WHERE id = $2
                """, [new_id, existing_row['id']])
            
            return str(new_id)
    
    async def get_phase_artifacts(
        self,
        project_id: str,
        phase: str,
        include_superseded: bool = False
    ) -> list[dict]:
        """Get all current artifacts for a phase."""
        superseded_filter = "" if include_superseded else "AND superseded_by IS NULL"
        
        async with self.pool.connection() as conn:
            results = await conn.execute(f"""
                SELECT id, agent_id, artifact_type, name, storage_path,
                       content_hash, size_bytes, metadata, created_at
                FROM artifacts
                WHERE project_id = $1 AND phase = $2 {superseded_filter}
                ORDER BY created_at DESC
            """, [project_id, phase])
            
            return [dict(row) for row in await results.fetchall()]
```

---

## 8. Infrastructure Design

### 8.1 Updated Docker Composition

**Current**: [`docker-compose.yml`](../../docker-compose.yml)

**Target docker-compose.yml**:

```yaml
version: '3.8'

services:
  # ===== Core Agent Services =====
  
  agent-supervisor:
    build:
      context: .
      dockerfile: Dockerfile
      target: agent
    container_name: sdlc-supervisor
    environment:
      - AGENT_ROLE=supervisor
      - POSTGRES_URL=postgresql://agent:agent@postgres:5432/sdlc_agent
      - REDIS_URL=redis://redis:6379
      - OTLP_ENDPOINT=http://otel-collector:4317
      - MCP_CONFIG_PATH=/app/config/mcp-servers.yaml
    volumes:
      - ./workspace:/workspace
      - ./config:/app/config:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - agent-network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

  agent-workers:
    build:
      context: .
      dockerfile: Dockerfile
      target: agent
    environment:
      - AGENT_ROLE=worker
      - POSTGRES_URL=postgresql://agent:agent@postgres:5432/sdlc_agent
      - REDIS_URL=redis://redis:6379
      - OTLP_ENDPOINT=http://otel-collector:4317
    volumes:
      - ./workspace:/workspace
      - ./config:/app/config:ro
    depends_on:
      - agent-supervisor
    networks:
      - agent-network
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 2G

  # ===== MCP Servers =====
  
  mcp-postgres:
    image: ghcr.io/anthropic/mcp-server-postgres:latest
    container_name: mcp-postgres
    environment:
      - DATABASE_URL=postgresql://agent:agent@postgres:5432/sdlc_agent
    networks:
      - agent-network
    ports:
      - "8081:8080"

  mcp-docker:
    image: ghcr.io/anthropic/mcp-server-docker:latest
    container_name: mcp-docker
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - agent-network
    ports:
      - "8082:8080"

  mcp-kubernetes:
    image: ghcr.io/anthropic/mcp-server-kubernetes:latest
    container_name: mcp-kubernetes
    volumes:
      - ~/.kube:/root/.kube:ro
    networks:
      - agent-network
    ports:
      - "8083:8080"

  # ===== Data Layer =====
  
  postgres:
    image: pgvector/pgvector:pg16
    container_name: sdlc-postgres
    environment:
      - POSTGRES_DB=sdlc_agent
      - POSTGRES_USER=agent
      - POSTGRES_PASSWORD=agent
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    networks:
      - agent-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d sdlc_agent"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: sdlc-redis
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    networks:
      - agent-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ===== Sandbox Execution =====
  
  sandbox-manager:
    build:
      context: ./sandbox
      dockerfile: Dockerfile
    container_name: sdlc-sandbox-manager
    privileged: true  # Required for container-in-container
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - sandbox-workspaces:/sandboxes
    environment:
      - MAX_SANDBOXES=10
      - SANDBOX_TIMEOUT=3600
      - SANDBOX_MEMORY_LIMIT=2g
      - SANDBOX_CPU_LIMIT=1
    networks:
      - agent-network
    ports:
      - "8090:8080"

  # ===== Observability Stack =====
  
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: sdlc-otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./config/otel-collector.yaml:/etc/otel-collector-config.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Prometheus metrics
    networks:
      - agent-network

  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: sdlc-jaeger
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"  # UI
      - "14268:14268"  # Collector
    networks:
      - agent-network

  prometheus:
    image: prom/prometheus:latest
    container_name: sdlc-prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - agent-network

  grafana:
    image: grafana/grafana:latest
    container_name: sdlc-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - agent-network
    depends_on:
      - prometheus
      - jaeger

  # ===== API Gateway =====
  
  api-gateway:
    image: nginx:alpine
    container_name: sdlc-gateway
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    ports:
      - "80:80"
      - "443:443"
    networks:
      - agent-network
    depends_on:
      - agent-supervisor

volumes:
  postgres-data:
  redis-data:
  prometheus-data:
  grafana-data:
  sandbox-workspaces:

networks:
  agent-network:
    driver: bridge
```

### 8.2 Sandbox Execution Strategy

```python
# src/agent/sandbox/manager.py

import docker
from pydantic import BaseModel

class SandboxConfig(BaseModel):
    """Configuration for a sandbox instance."""
    image: str = "python:3.11-slim"
    memory_limit: str = "2g"
    cpu_limit: float = 1.0
    timeout: int = 3600
    network_mode: str = "none"  # Isolated by default
    read_only_root: bool = True
    working_dir: str = "/workspace"

class SandboxManager:
    """Manages sandboxed execution environments."""
    
    def __init__(self, docker_url: str = "unix:///var/run/docker.sock"):
        self.client = docker.DockerClient(base_url=docker_url)
        self.sandboxes: dict[str, docker.models.containers.Container] = {}
    
    async def create_sandbox(
        self,
        sandbox_id: str,
        config: SandboxConfig,
        mount_workspace: str | None = None
    ) -> str:
        """Create a new sandbox container."""
        volumes = {}
        if mount_workspace:
            volumes[mount_workspace] = {
                'bind': config.working_dir,
                'mode': 'rw'
            }
        
        container = self.client.containers.create(
            image=config.image,
            name=f"sandbox-{sandbox_id}",
            detach=True,
            mem_limit=config.memory_limit,
            cpu_quota=int(config.cpu_limit * 100000),
            network_mode=config.network_mode,
            read_only=config.read_only_root,
            working_dir=config.working_dir,
            volumes=volumes,
            security_opt=[
                "no-new-privileges:true",
                "seccomp=unconfined"  # Or use custom seccomp profile
            ],
            tmpfs={'/tmp': 'size=512m,mode=1777'}
        )
        
        container.start()
        self.sandboxes[sandbox_id] = container
        return container.id
    
    async def execute_in_sandbox(
        self,
        sandbox_id: str,
        command: str,
        timeout: int = 60
    ) -> tuple[int, str, str]:
        """Execute a command in a sandbox."""
        container = self.sandboxes.get(sandbox_id)
        if not container:
            raise ValueError(f"Sandbox {sandbox_id} not found")
        
        exec_result = container.exec_run(
            cmd=["bash", "-c", command],
            workdir="/workspace",
            demux=True
        )
        
        exit_code = exec_result.exit_code
        stdout = exec_result.output[0].decode() if exec_result.output[0] else ""
        stderr = exec_result.output[1].decode() if exec_result.output[1] else ""
        
        return exit_code, stdout, stderr
    
    async def destroy_sandbox(self, sandbox_id: str):
        """Stop and remove a sandbox container."""
        container = self.sandboxes.pop(sandbox_id, None)
        if container:
            container.stop(timeout=5)
            container.remove(force=True)
```

### 8.3 Observability Stack

**Migration from**: [`TracingManager`](../../src/agent/observability/tracing.py:21)

The observability stack includes:

1. **OpenTelemetry Collector** - Central telemetry pipeline
2. **Jaeger** - Distributed tracing UI
3. **Prometheus** - Metrics collection
4. **Grafana** - Dashboards and alerting

```yaml
# config/otel-collector.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  
  attributes:
    actions:
      - key: service.name
        from_attribute: service_name
        action: upsert

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  
  prometheus:
    endpoint: "0.0.0.0:8888"
    namespace: sdlc_agent
  
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, attributes]
      exporters: [jaeger, logging]
    
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

---

## 9. Migration Plan

### 9.1 Gap Analysis: Current vs Target

| Component | Current State | Target State | Gap |
|-----------|--------------|--------------|-----|
| **Agent Orchestration** | Custom `AgentOrchestrator` with sequential execution | LangGraph StateGraph with supervisor/swarm patterns | Major refactor |
| **Reasoning Engine** | Custom `ReActEngine` with manual loops | LangGraph-native nodes with streaming | Major refactor |
| **Tool Integration** | Custom `BaseTool` + `ToolRegistry` | MCP servers via `langchain-mcp-adapters` | Full migration |
| **Vector Store** | Qdrant via `QdrantVectorStore` | PostgreSQL + pgvector | Migration required |
| **Checkpointing** | Custom session checkpoints | LangGraph `PostgresSaver` | Replacement |
| **Memory Tiers** | Working + Episodic + Procedural (partial) | Three-tier PostgreSQL-based | Enhancement |
| **SDLC Agents** | 6 agents (Req, Arch, Impl, Test, Deploy, Ops) | 8 agents (+ System Design, CI/CD) | Addition |
| **Tracing** | OpenTelemetry decorators | Full OTLP collector pipeline | Enhancement |
| **Sandbox** | Planned Docker integration | Docker manager + optional Firecracker | Implementation |

### 9.2 Phase-by-Phase Migration

#### Phase M1: Foundation (Weeks 1-2)

**Objective**: Set up LangGraph and PostgreSQL infrastructure

```mermaid
gantt
    title Phase M1: Foundation
    dateFormat  YYYY-MM-DD
    section Database
    Setup pgvector PostgreSQL    :m1a, 2026-02-07, 3d
    Migrate schema              :m1b, after m1a, 2d
    section LangGraph
    Install LangGraph v1.0.7    :m1c, 2026-02-07, 1d
    Create SDLCState TypedDict  :m1d, after m1c, 2d
    Implement PostgresSaver     :m1e, after m1d, 2d
    section Testing
    Unit tests for state        :m1f, after m1e, 2d
```

**Tasks**:
- [ ] Install `langgraph==1.0.7`, `langgraph-checkpoint-postgres`, `pgvector`
- [ ] Set up PostgreSQL with pgvector extension
- [ ] Define `SDLCState` TypedDict schema
- [ ] Implement `PostgresSaver` checkpoint integration
- [ ] Create database migration scripts
- [ ] Write unit tests for state management

#### Phase M2: MCP Integration (Weeks 3-4)

**Objective**: Migrate all tools to MCP servers

```mermaid
gantt
    title Phase M2: MCP Integration
    dateFormat  YYYY-MM-DD
    section MCP Servers
    Configure MCP servers       :m2a, 2026-02-21, 2d
    Implement MCPToolLoader     :m2b, after m2a, 3d
    section Migration
    Migrate filesystem tools    :m2c, after m2b, 2d
    Migrate git tools           :m2d, after m2c, 2d
    Migrate shell tools         :m2e, after m2d, 2d
    section Testing
    Integration tests           :m2f, after m2e, 3d
```

**Tasks**:
- [ ] Install `mcp`, `langchain-mcp-adapters`
- [ ] Create `MCPServerConfig` for all servers
- [ ] Implement `MCPToolLoader` class
- [ ] Migrate `filesystem/` tools to MCP
- [ ] Migrate `git/` tools to MCP
- [ ] Migrate `shell/` tools to MCP
- [ ] Add MCP servers to docker-compose
- [ ] Write integration tests

#### Phase M3: Agent Migration (Weeks 5-7)

**Objective**: Migrate agents to LangGraph nodes

```mermaid
gantt
    title Phase M3: Agent Migration
    dateFormat  YYYY-MM-DD
    section Supervisor
    Implement supervisor node   :m3a, 2026-03-07, 3d
    Add routing logic           :m3b, after m3a, 2d
    section Worker Agents
    Migrate Requirements Agent  :m3c, after m3b, 2d
    Create System Design Agent  :m3d, after m3c, 2d
    Migrate Architecture Agent  :m3e, after m3d, 2d
    Create Coding Pool          :m3f, after m3e, 3d
    Migrate Testing Agent       :m3g, after m3f, 2d
    Create CI/CD Agent          :m3h, after m3g, 2d
    Migrate Deployment Agent    :m3i, after m3h, 2d
    Create Monitoring Agent     :m3j, after m3i, 2d
    section Swarm
    Implement code-test swarm   :m3k, after m3j, 3d
```

**Tasks**:
- [ ] Create supervisor node with routing function
- [ ] Define human approval interrupt nodes
- [ ] Migrate `RequirementsAgent` → `requirements_node`
- [ ] Create new `system_design_node`
- [ ] Migrate `ArchitectureAgent` → `architecture_node`
- [ ] Implement `coding_pool` with dynamic scaling
- [ ] Migrate `TestingAgent` → `testing_node`
- [ ] Create new `cicd_node`
- [ ] Migrate `DeploymentAgent` → `deployment_node`
- [ ] Create new `monitoring_node`
- [ ] Implement swarm pattern for code-test loop

#### Phase M4: Memory Migration (Weeks 8-9)

**Objective**: Implement three-tier memory architecture

```mermaid
gantt
    title Phase M4: Memory Migration
    dateFormat  YYYY-MM-DD
    section Tier 1
    Migrate to PostgresSaver    :m4a, 2026-04-04, 2d
    section Tier 2
    Implement pgvector semantic :m4b, after m4a, 3d
    Migrate from Qdrant         :m4c, after m4b, 2d
    section Tier 3
    Implement procedural memory :m4d, after m4c, 3d
    section Artifacts
    Implement ArtifactStore     :m4e, after m4d, 2d
```

**Tasks**:
- [ ] Migrate episodic memory to `PostgresSaver`
- [ ] Implement `SemanticMemoryV2` with pgvector
- [ ] Create data migration script from Qdrant
- [ ] Implement `ProceduralMemoryV2`
- [ ] Create `ArtifactStore` for cross-agent communication
- [ ] Write memory integration tests

#### Phase M5: A2A Protocol (Week 10)

**Objective**: Implement A2A for external agent communication

```mermaid
gantt
    title Phase M5: A2A Protocol
    dateFormat  YYYY-MM-DD
    section Implementation
    Define Agent Cards          :m5a, 2026-04-18, 2d
    Implement task lifecycle    :m5b, after m5a, 3d
    Create LangGraph bridge     :m5c, after m5b, 2d
```

**Tasks**:
- [ ] Define `AgentCard` schemas for all agents
- [ ] Implement `A2ATask` state machine
- [ ] Create `A2ATaskManager`
- [ ] Implement `LangGraphA2ABridge`
- [ ] Add API endpoints for A2A communication

#### Phase M6: Infrastructure & Testing (Weeks 11-12)

**Objective**: Complete infrastructure and comprehensive testing

```mermaid
gantt
    title Phase M6: Infrastructure & Testing
    dateFormat  YYYY-MM-DD
    section Infrastructure
    Update docker-compose       :m6a, 2026-05-02, 2d
    Implement SandboxManager    :m6b, after m6a, 3d
    Configure observability     :m6c, after m6b, 2d
    section Testing
    E2E workflow tests          :m6d, after m6c, 3d
    Performance testing         :m6e, after m6d, 2d
    Security audit              :m6f, after m6e, 2d
```

**Tasks**:
- [ ] Update `docker-compose.yml` with all services
- [ ] Implement `SandboxManager` for code execution
- [ ] Configure OpenTelemetry collector pipeline
- [ ] Create Grafana dashboards
- [ ] Write E2E tests for full SDLC workflow
- [ ] Perform load testing
- [ ] Conduct security audit

### 9.3 Rollback Strategy

Each phase includes rollback capabilities:

1. **Database**: All migrations are reversible with down scripts
2. **Code**: Feature flags enable gradual rollout
3. **Infrastructure**: Blue-green deployment for zero-downtime updates

```python
# config/feature_flags.py

FEATURE_FLAGS = {
    "use_langgraph_supervisor": False,  # Enable after Phase M3
    "use_mcp_tools": False,              # Enable after Phase M2
    "use_pgvector_memory": False,        # Enable after Phase M4
    "use_a2a_protocol": False,           # Enable after Phase M5
}
```

---

## 10. Technology Stack Summary

### 10.1 Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `langgraph` | `1.0.7` | Agent orchestration |
| `langgraph-checkpoint-postgres` | `^2.0.0` | State persistence |
| `langchain-core` | `^0.3.0` | Base abstractions |
| `langchain-openai` | `^0.2.0` | OpenAI integration |
| `langchain-mcp-adapters` | `^0.1.0` | MCP tool loading |
| `mcp` | `^1.0.0` | MCP protocol client |
| `psycopg[pool]` | `^3.2.0` | PostgreSQL driver |
| `pgvector` | `^0.3.0` | Vector operations |
| `opentelemetry-sdk` | `^1.27.0` | Observability |
| `pydantic` | `^2.9.0` | Data validation |
| `fastapi` | `^0.115.0` | API framework |
| `docker` | `^7.1.0` | Container management |

### 10.2 MCP Server Stack

| Server | Package | Transport |
|--------|---------|-----------|
| Filesystem | `@anthropic/mcp-server-filesystem` | stdio |
| Git | `@anthropic/mcp-server-git` | stdio |
| GitHub | `@anthropic/mcp-server-github` | stdio |
| Shell | `@anthropic/mcp-server-shell` | stdio |
| Memory | `@anthropic/mcp-server-memory` | stdio |
| Fetch | `@anthropic/mcp-server-fetch` | stdio |
| PostgreSQL | `@anthropic/mcp-server-postgres` | HTTP/SSE |
| Docker | `@anthropic/mcp-server-docker` | HTTP/SSE |
| Kubernetes | `@anthropic/mcp-server-kubernetes` | HTTP/SSE |
| Puppeteer | `@anthropic/mcp-server-puppeteer` | stdio |

### 10.3 Infrastructure Stack

| Component | Image/Version | Purpose |
|-----------|---------------|---------|
| PostgreSQL | `pgvector/pgvector:pg16` | Primary database + vectors |
| Redis | `redis:7-alpine` | Caching + pub/sub |
| OpenTelemetry Collector | `otel/opentelemetry-collector-contrib` | Telemetry pipeline |
| Jaeger | `jaegertracing/all-in-one` | Distributed tracing |
| Prometheus | `prom/prometheus` | Metrics collection |
| Grafana | `grafana/grafana` | Dashboards |
| Nginx | `nginx:alpine` | API gateway |

### 10.4 Development Tools

| Tool | Purpose |
|------|---------|
| `pytest` | Testing framework |
| `pytest-asyncio` | Async test support |
| `ruff` | Linting |
| `black` | Code formatting |
| `mypy` | Type checking |
| `pre-commit` | Git hooks |

---

## Appendix A: File Structure (Target)

```
autonomous-dev-agent/
├── src/
│   └── agent/
│       ├── __init__.py
│       ├── langgraph/
│       │   ├── __init__.py
│       │   ├── state.py          # SDLCState TypedDict
│       │   ├── supervisor.py     # Supervisor node
│       │   ├── nodes/            # Agent nodes
│       │   │   ├── requirements.py
│       │   │   ├── system_design.py
│       │   │   ├── architecture.py
│       │   │   ├── coding.py
│       │   │   ├── testing.py
│       │   │   ├── cicd.py
│       │   │   ├── deployment.py
│       │   │   └── monitoring.py
│       │   ├── swarm.py          # Swarm patterns
│       │   ├── approval.py       # Human-in-the-loop
│       │   └── persistence.py    # PostgresSaver wrapper
│       │
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── config.py         # Server configurations
│       │   ├── loader.py         # Tool loading
│       │   └── servers/          # Custom MCP servers
│       │
│       ├── a2a/
│       │   ├── __init__.py
│       │   ├── cards.py          # Agent Cards
│       │   ├── task.py           # Task lifecycle
│       │   └── bridge.py         # LangGraph bridge
│       │
│       ├── memory/
│       │   ├── __init__.py
│       │   └── v2/
│       │       ├── episodic.py   # Tier 1
│       │       ├── semantic.py   # Tier 2
│       │       ├── procedural.py # Tier 3
│       │       └── artifacts.py  # Artifact store
│       │
│       ├── sandbox/
│       │   ├── __init__.py
│       │   └── manager.py        # Sandbox orchestration
│       │
│       ├── observability/
│       │   └── ...               # Existing + enhancements
│       │
│       └── api/
│           └── ...               # REST/WebSocket endpoints
│
├── config/
│   ├── mcp-servers.yaml
│   ├── otel-collector.yaml
│   ├── prometheus.yml
│   └── grafana/
│
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## Appendix B: References

1. [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
2. [MCP Specification](https://spec.modelcontextprotocol.io/)
3. [A2A Protocol Draft](https://google.github.io/a2a-spec/)
4. [pgvector Documentation](https://github.com/pgvector/pgvector)
5. [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)

---

*Document generated by Autonomous AI Agent Framework Architecture Team*
