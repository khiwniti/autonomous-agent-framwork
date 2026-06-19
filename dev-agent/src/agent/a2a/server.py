"""A2A Server Implementation.

Provides HTTP server wrapper that exposes LangGraph agents via A2A protocol,
enabling inter-agent communication through standardized JSON-RPC 2.0 endpoints.

Endpoints (per A2A spec):
- GET /.well-known/agent.json - Agent Card discovery
- POST /tasks/send - Create new task (non-streaming)
- POST /tasks/sendSubscribe - Create task with SSE streaming
- GET /tasks/{id} - Get task status
- POST /tasks/{id}/cancel - Cancel task
"""

import asyncio
import json
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel, Field

from .agent_card import AgentCard, AgentSkill, get_skills_for_phase
from .task import Artifact, TaskManager, TaskState, TaskStatus


class TaskSendRequest(BaseModel):
    """Request body for /tasks/send and /tasks/sendSubscribe."""
    
    message: str = Field(description="Task message/request")
    session_id: str | None = Field(default=None, description="Session for multi-turn")
    skill_id: str | None = Field(default=None, description="Target skill ID")
    params: dict[str, Any] | None = Field(default=None, description="Additional params")


class TaskSendResponse(BaseModel):
    """Response from /tasks/send."""
    
    id: str = Field(description="Task ID")
    session_id: str = Field(description="Session ID")
    status: TaskStatus = Field(description="Task status")


class A2AServer:
    """
    A2A protocol server wrapper for LangGraph agents.
    
    Exposes any LangGraph-based agent via standardized A2A endpoints,
    enabling agent-to-agent communication through HTTP/JSON-RPC.
    
    Usage:
        # Create agent card
        card = create_agent_card(...)
        
        # Create server
        server = A2AServer(card, task_handler)
        
        # Run with ASGI server
        import uvicorn
        uvicorn.run(server.app, host="0.0.0.0", port=8000)
    """
    
    def __init__(
        self,
        agent_card: AgentCard,
        task_handler: Callable[[TaskState], AsyncGenerator[TaskState, None]] | None = None,
    ):
        """
        Initialize A2A server.
        
        Args:
            agent_card: Agent Card for capability advertisement
            task_handler: Async generator function that processes tasks
        """
        self.agent_card = agent_card
        self.task_manager = TaskManager()
        self._task_handler = task_handler
        self._app = None
    
    @property
    def app(self):
        """Get FastAPI/Starlette app."""
        if self._app is None:
            self._app = self._create_app()
        return self._app
    
    def _create_app(self):
        """Create FastAPI application with A2A endpoints."""
        try:
            from fastapi import FastAPI, HTTPException, Request
            from fastapi.responses import JSONResponse, StreamingResponse
        except ImportError:
            raise ImportError("FastAPI is required for A2A server. Install with: pip install fastapi")
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            yield
            # Shutdown - cleanup
        
        app = FastAPI(
            title=self.agent_card.name,
            description=self.agent_card.description,
            version=self.agent_card.version,
            lifespan=lifespan,
        )
        
        # =====================================================================
        # Agent Card Discovery
        # =====================================================================
        
        @app.get("/.well-known/agent.json")
        async def get_agent_card():
            """Return Agent Card for capability discovery."""
            return JSONResponse(
                content=self.agent_card.to_wellknown_json(),
                media_type="application/json",
            )
        
        # =====================================================================
        # Task Endpoints
        # =====================================================================
        
        @app.post("/tasks/send", response_model=TaskSendResponse)
        async def send_task(request: TaskSendRequest):
            """
            Create and process a task (non-streaming).
            
            The task is processed to completion before returning.
            """
            task = await self.task_manager.create_task(
                initial_message=request.message,
                session_id=request.session_id,
                agent_id=self.agent_card.name,
                skill_id=request.skill_id,
            )
            
            # Process task
            if self._task_handler:
                try:
                    await self.task_manager.update_status(task.id, TaskStatus.WORKING)
                    
                    async for updated_task in self._task_handler(task):
                        task = updated_task
                    
                    if task.status == TaskStatus.WORKING:
                        await self.task_manager.complete_task(task.id)
                except Exception as e:
                    await self.task_manager.fail_task(task.id, str(e))
            
            task = await self.task_manager.get_task(task.id)
            return TaskSendResponse(
                id=task.id,
                session_id=task.session_id,
                status=task.status,
            )
        
        @app.post("/tasks/sendSubscribe")
        async def send_task_subscribe(request: TaskSendRequest):
            """
            Create and process a task with SSE streaming.
            
            Returns Server-Sent Events for real-time updates.
            """
            task = await self.task_manager.create_task(
                initial_message=request.message,
                session_id=request.session_id,
                agent_id=self.agent_card.name,
                skill_id=request.skill_id,
            )
            
            async def event_stream():
                # Subscribe to task events
                async for event in self.task_manager.subscribe(task.id):
                    yield event.to_sse()
            
            # Start processing in background
            if self._task_handler:
                asyncio.create_task(self._process_task_async(task))
            
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        
        @app.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            """Get task status and details."""
            task = await self.task_manager.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task.model_dump(mode="json")
        
        @app.post("/tasks/{task_id}/cancel")
        async def cancel_task(task_id: str):
            """Cancel a running task."""
            task = await self.task_manager.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED):
                raise HTTPException(status_code=400, detail="Task already finished")
            
            await self.task_manager.update_status(task_id, TaskStatus.CANCELED)
            return {"status": "canceled"}
        
        @app.post("/tasks/{task_id}/input")
        async def provide_input(task_id: str, request: Request):
            """Provide input for a paused task (human-in-the-loop)."""
            body = await request.json()
            user_input = body.get("input", "")
            
            task = await self.task_manager.provide_input(task_id, user_input)
            if not task:
                raise HTTPException(status_code=400, detail="Task not awaiting input")
            
            # Resume processing
            if self._task_handler:
                asyncio.create_task(self._process_task_async(task))
            
            return {"status": "resumed"}
        
        # =====================================================================
        # Health & Readiness
        # =====================================================================
        
        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy"}
        
        @app.get("/ready")
        async def ready():
            """Readiness check endpoint."""
            return {"status": "ready"}
        
        return app
    
    async def _process_task_async(self, task: TaskState) -> None:
        """Process task asynchronously."""
        if not self._task_handler:
            return
        
        try:
            await self.task_manager.update_status(task.id, TaskStatus.WORKING)
            
            async for updated_task in self._task_handler(task):
                # Check for cancellation
                current = await self.task_manager.get_task(task.id)
                if current and current.status == TaskStatus.CANCELED:
                    return
                task = updated_task
            
            # Complete if still working
            current = await self.task_manager.get_task(task.id)
            if current and current.status == TaskStatus.WORKING:
                await self.task_manager.complete_task(task.id)
        except Exception as e:
            await self.task_manager.fail_task(task.id, str(e))
    
    def set_task_handler(
        self,
        handler: Callable[[TaskState], AsyncGenerator[TaskState, None]],
    ) -> None:
        """Set the task handler function."""
        self._task_handler = handler


def expose_langgraph_agent(
    graph,
    agent_name: str,
    agent_description: str,
    base_url: str,
    phase: str | None = None,
    skills: list[AgentSkill] | None = None,
) -> A2AServer:
    """
    Expose a LangGraph agent via A2A protocol.
    
    This is the primary integration point between LangGraph and A2A.
    It wraps a LangGraph CompiledGraph in an A2A server.
    
    Args:
        graph: LangGraph CompiledGraph
        agent_name: Agent name for discovery
        agent_description: Agent description
        base_url: Base URL for A2A endpoints
        phase: SDLC phase (uses pre-defined skills if set)
        skills: Custom skills (overrides phase skills)
        
    Returns:
        Configured A2AServer
        
    Example:
        from langgraph.graph import StateGraph
        
        # Build your graph
        graph = StateGraph(State)
        ...
        compiled = graph.compile()
        
        # Expose via A2A
        server = expose_langgraph_agent(
            compiled,
            agent_name="Requirements Agent",
            agent_description="Analyzes requirements",
            base_url="http://localhost:8000",
            phase="requirements",
        )
    """
    # Determine skills
    if skills is None and phase:
        skills = get_skills_for_phase(phase)
    skills = skills or []
    
    # Create Agent Card
    from .agent_card import A2ACapability, create_agent_card
    
    card = create_agent_card(
        name=agent_name,
        description=agent_description,
        url=base_url,
        skills=skills,
        capabilities=[
            A2ACapability.STREAMING,
            A2ACapability.STATE_PERSISTENCE,
            A2ACapability.HUMAN_IN_LOOP,
        ],
    )
    
    # Create task handler that invokes LangGraph
    async def langgraph_task_handler(task: TaskState) -> AsyncGenerator[TaskState, None]:
        """Process task through LangGraph workflow."""
        # Prepare input for LangGraph
        input_data = {
            "messages": [{"role": "user", "content": task.get_text_content()}],
            "task_id": task.id,
            "session_id": task.session_id,
        }
        
        # Check if graph supports streaming
        if hasattr(graph, "astream"):
            async for chunk in graph.astream(input_data):
                # Extract updates from streaming chunk
                if isinstance(chunk, dict):
                    for node_name, node_output in chunk.items():
                        if isinstance(node_output, dict):
                            # Check for messages
                            if "messages" in node_output:
                                for msg in node_output["messages"]:
                                    if hasattr(msg, "content"):
                                        task.add_message(
                                            TaskMessage.agent_text(msg.content)
                                        )
                            
                            # Check for artifacts
                            if "artifacts" in node_output:
                                for art in node_output["artifacts"]:
                                    task.add_artifact(Artifact(**art))
                
                yield task
        else:
            # Non-streaming invocation
            result = await graph.ainvoke(input_data)
            
            # Process result
            if isinstance(result, dict):
                if "messages" in result:
                    for msg in result["messages"]:
                        if hasattr(msg, "content"):
                            task.add_message(TaskMessage.agent_text(msg.content))
                
                if "artifacts" in result:
                    for art in result["artifacts"]:
                        task.add_artifact(Artifact(**art))
            
            yield task
    
    # Need to import TaskMessage here to avoid circular import
    from .task import TaskMessage
    
    server = A2AServer(card, langgraph_task_handler)
    return server


def create_a2a_server(
    agent_card: AgentCard,
    task_handler: Callable[[TaskState], AsyncGenerator[TaskState, None]] | None = None,
) -> A2AServer:
    """
    Create an A2A server with custom configuration.
    
    Lower-level factory for custom server setups.
    
    Args:
        agent_card: Agent Card configuration
        task_handler: Optional task processing function
        
    Returns:
        Configured A2AServer
    """
    return A2AServer(agent_card, task_handler)
