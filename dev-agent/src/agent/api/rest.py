"""REST API server with FastAPI - Phase 5."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.agents.base import AgentRole, AgentTask
from agent.api.schemas import (
    AgentExecutionRequest,
    WorkflowExecutionRequest,
    SessionCreateRequest,
    ChatMessageRequest,
    TaskStatusResponse,
    WorkflowStatusResponse,
    SessionResponse,
    ChatMessageResponse,
    ErrorResponse,
    HealthResponse,
    PaginationParams,
    PaginatedResponse,
)
from agent.core.orchestrator import AgentOrchestrator, WorkflowStage, create_orchestrator
from agent.llm.base import BaseLLMClient
from agent.session.manager import SessionManager
from agent.tools.base import ToolRegistry


class AgentAPI:
    """REST API for autonomous agent system."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        tool_registry: ToolRegistry,
        session_manager: SessionManager | None = None,
    ):
        """Initialize API server.

        Args:
            llm_client: LLM client for agents
            tool_registry: Tool registry
            session_manager: Session manager (optional)

        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.session_manager = session_manager or SessionManager()
        self.orchestrator: AgentOrchestrator | None = None

        # Create FastAPI app
        self.app = FastAPI(
            title="Autonomous Agent API",
            description="REST API for autonomous software development agent",
            version="1.0.0",
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure based on environment
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register routes
        self._register_routes()

        # Exception handlers
        self._register_exception_handlers()

    async def initialize(self) -> None:
        """Initialize API components."""
        # Create orchestrator with all agents
        self.orchestrator = await create_orchestrator(
            self.llm_client, self.tool_registry
        )

    def _register_routes(self) -> None:
        """Register API routes."""

        @self.app.on_event("startup")
        async def startup():
            await self.initialize()

        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            return HealthResponse(
                status="healthy",
                version="1.0.0",
                components={
                    "api": "healthy",
                    "orchestrator": "healthy" if self.orchestrator else "initializing",
                    "sessions": "healthy",
                },
            )

        @self.app.post("/sessions", response_model=SessionResponse)
        async def create_session(request: SessionCreateRequest):
            """Create a new session."""
            session = await self.session_manager.create_session(
                name=request.name, metadata=request.metadata
            )
            return SessionResponse(
                session_id=session.id,
                name=session.name,
                created_at=session.created_at,
                last_activity=session.last_activity,
                task_count=len(session.tasks),
                metadata=session.metadata,
            )

        @self.app.get("/sessions/{session_id}", response_model=SessionResponse)
        async def get_session(session_id: str):
            """Get session information."""
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            return SessionResponse(
                session_id=session.id,
                name=session.name,
                created_at=session.created_at,
                last_activity=session.last_activity,
                task_count=len(session.tasks),
                metadata=session.metadata,
            )

        @self.app.get("/sessions", response_model=PaginatedResponse)
        async def list_sessions(pagination: PaginationParams = Depends()):
            """List all sessions."""
            sessions = await self.session_manager.list_sessions(
                page=pagination.page, page_size=pagination.page_size
            )
            total = await self.session_manager.count_sessions()

            return PaginatedResponse(
                items=[
                    SessionResponse(
                        session_id=s.id,
                        name=s.name,
                        created_at=s.created_at,
                        last_activity=s.last_activity,
                        task_count=len(s.tasks),
                        metadata=s.metadata,
                    )
                    for s in sessions
                ],
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=(total + pagination.page_size - 1) // pagination.page_size,
            )

        @self.app.delete("/sessions/{session_id}")
        async def delete_session(session_id: str):
            """Delete a session."""
            await self.session_manager.delete_session(session_id)
            return {"message": "Session deleted"}

        @self.app.post("/agents/execute", response_model=TaskStatusResponse)
        async def execute_agent(
            request: AgentExecutionRequest, background_tasks: BackgroundTasks
        ):
            """Execute an agent task."""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")

            # Map string role to AgentRole enum
            try:
                role = AgentRole(request.agent_role)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid agent role: {request.agent_role}",
                )

            # Create task
            task_id = f"task_{datetime.now(timezone.utc).timestamp()}"
            task = AgentTask(
                id=task_id,
                role=role,
                objective=request.objective,
                context=request.context,
            )

            # Get appropriate agent
            agent = self.orchestrator.agents.get(role)
            if not agent:
                raise HTTPException(
                    status_code=404, detail=f"No agent registered for role {role}"
                )

            # Execute task in background
            background_tasks.add_task(self._execute_task_background, agent, task, request.session_id)

            # Return immediate response
            return TaskStatusResponse(
                task_id=task.id,
                status=task.status.value,
                agent_role=task.role.value,
                objective=task.objective,
                started_at=None,
                completed_at=None,
                error=None,
                result=None,
            )

        @self.app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
        async def get_task_status(task_id: str):
            """Get task status."""
            # In production, store tasks in database or cache
            # For now, return placeholder
            raise HTTPException(
                status_code=501, detail="Task status lookup not yet implemented"
            )

        @self.app.post("/workflows/execute", response_model=WorkflowStatusResponse)
        async def execute_workflow(
            request: WorkflowExecutionRequest, background_tasks: BackgroundTasks
        ):
            """Execute a workflow."""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")

            # Parse stages
            stages = []
            if request.stages:
                for stage_name in request.stages:
                    try:
                        stages.append(WorkflowStage(stage_name))
                    except ValueError:
                        raise HTTPException(
                            status_code=400, detail=f"Invalid stage: {stage_name}"
                        )

            # Create workflow
            workflow = await self.orchestrator.create_workflow(
                name=request.name,
                objective=request.objective,
                stages=stages if stages else None,
                context=request.context,
            )

            # Execute in background
            background_tasks.add_task(
                self._execute_workflow_background, workflow.id, request.session_id
            )

            # Return immediate response
            return WorkflowStatusResponse(
                workflow_id=workflow.id,
                name=workflow.name,
                status=workflow.status.value,
                current_stage=None,
                completed_stages=[],
                failed_stages=[],
                progress=0.0,
                error=None,
            )

        @self.app.get("/workflows/{workflow_id}", response_model=WorkflowStatusResponse)
        async def get_workflow_status(workflow_id: str):
            """Get workflow status."""
            if not self.orchestrator:
                raise HTTPException(status_code=503, detail="Orchestrator not initialized")

            workflow = self.orchestrator.workflows.get(workflow_id)
            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")

            status = await self.orchestrator.get_workflow_status(workflow_id)

            return WorkflowStatusResponse(
                workflow_id=workflow.id,
                name=workflow.name,
                status=workflow.status.value,
                current_stage=workflow.current_stage.value if workflow.current_stage else None,
                completed_stages=[s.value for s in status["completed_stages"]],
                failed_stages=[s.value for s in status["failed_stages"]],
                progress=status["progress"],
                error=workflow.error,
            )

        @self.app.post("/chat", response_model=ChatMessageResponse)
        async def send_chat_message(request: ChatMessageRequest):
            """Send a chat message (non-streaming)."""
            # Get or create session
            session = await self.session_manager.get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            # Add user message to session
            message_id = f"msg_{datetime.now(timezone.utc).timestamp()}"
            await session.add_message("user", request.message)

            # Process message (placeholder - integrate with agent execution)
            response_content = f"Echo: {request.message}"

            # Add assistant response to session
            await session.add_message("assistant", response_content)

            return ChatMessageResponse(
                message_id=message_id,
                session_id=session.id,
                role="assistant",
                content=response_content,
                timestamp=datetime.now(timezone.utc),
                metadata={},
            )

    async def _execute_task_background(
        self, agent: Any, task: AgentTask, session_id: str | None
    ) -> None:
        """Execute task in background.

        Args:
            agent: Agent to execute task
            task: Task to execute
            session_id: Optional session ID

        """
        try:
            result = await agent.process_task(task)

            # Store result in session if session_id provided
            if session_id:
                session = await self.session_manager.get_session(session_id)
                if session:
                    await session.add_task(result)

        except Exception as e:
            # Log error (in production, use proper logging)
            print(f"Task {task.id} failed: {e}")

    async def _execute_workflow_background(
        self, workflow_id: str, session_id: str | None
    ) -> None:
        """Execute workflow in background.

        Args:
            workflow_id: Workflow to execute
            session_id: Optional session ID

        """
        try:
            if not self.orchestrator:
                return

            result = await self.orchestrator.execute_workflow(workflow_id)

            # Store result in session if session_id provided
            if session_id:
                session = await self.session_manager.get_session(session_id)
                if session:
                    # Add all workflow tasks to session
                    for task in result.tasks:
                        await session.add_task(task)

        except Exception as e:
            # Log error (in production, use proper logging)
            print(f"Workflow {workflow_id} failed: {e}")

    def _register_exception_handlers(self) -> None:
        """Register exception handlers."""

        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(
                    error="http_error",
                    message=exc.detail,
                    details={"status_code": exc.status_code},
                ).model_dump(),
            )

        @self.app.exception_handler(Exception)
        async def general_exception_handler(request, exc: Exception):
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    error="internal_error",
                    message=str(exc),
                    details={"type": type(exc).__name__},
                ).model_dump(),
            )


async def create_api(
    llm_client: BaseLLMClient,
    tool_registry: ToolRegistry,
    session_manager: SessionManager | None = None,
) -> AgentAPI:
    """Factory function to create configured API.

    Args:
        llm_client: LLM client
        tool_registry: Tool registry
        session_manager: Session manager

    Returns:
        Configured API instance

    """
    api = AgentAPI(llm_client, tool_registry, session_manager)
    await api.initialize()
    return api


# Module-level app instance for uvicorn
# Create with minimal dependencies - orchestrator initializes on startup
def _create_module_app() -> FastAPI:
    """Create module-level FastAPI app for uvicorn."""
    import os
    from agent.llm.openai_client import OpenAIClient

    # Create LLM client with environment config
    llm_client = OpenAIClient(
        api_key=os.getenv("OPENAI_API_KEY", "dummy-key"),
        api_base=os.getenv("OPENAI_API_BASE"),
    )

    # Create empty tool registry (tools will be registered on demand)
    tool_registry = ToolRegistry()

    # Create API instance
    api_instance = AgentAPI(llm_client, tool_registry)

    return api_instance.app


# Export app for uvicorn
app = _create_module_app()
