"""WebSocket API for streaming agent responses - Phase 5."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.websockets import WebSocketState

from agent.agents.base import AgentRole, AgentTask, TaskStatus
from agent.api.schemas import (
    WebSocketMessage,
    WebSocketMessageType,
    TaskProgressData,
    WorkflowProgressData,
    ChatChunkData,
)
from agent.core.orchestrator import AgentOrchestrator, WorkflowStage
from agent.session.manager import SessionManager


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: dict[str, WebSocket] = {}
        self.session_connections: dict[str, set[str]] = {}  # session_id -> connection_ids

    async def connect(self, websocket: WebSocket, connection_id: str, session_id: str | None = None) -> None:
        """Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection ID
            session_id: Optional session ID

        """
        await websocket.accept()
        self.active_connections[connection_id] = websocket

        if session_id:
            if session_id not in self.session_connections:
                self.session_connections[session_id] = set()
            self.session_connections[session_id].add(connection_id)

    def disconnect(self, connection_id: str, session_id: str | None = None) -> None:
        """Disconnect a WebSocket connection.

        Args:
            connection_id: Connection ID
            session_id: Optional session ID

        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if session_id and connection_id in self.session_connections.get(session_id, set()):
            self.session_connections[session_id].remove(connection_id)
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]

    async def send_message(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send a message to a specific connection.

        Args:
            connection_id: Connection ID
            message: Message to send

        Returns:
            True if sent successfully, False otherwise

        """
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return False

        try:
            await websocket.send_json(message.model_dump())
            return True
        except Exception:
            return False

    async def broadcast_to_session(self, session_id: str, message: WebSocketMessage) -> int:
        """Broadcast a message to all connections in a session.

        Args:
            session_id: Session ID
            message: Message to broadcast

        Returns:
            Number of successful sends

        """
        connection_ids = self.session_connections.get(session_id, set())
        success_count = 0

        for connection_id in connection_ids:
            if await self.send_message(connection_id, message):
                success_count += 1

        return success_count

    async def send_heartbeat(self, connection_id: str) -> bool:
        """Send a heartbeat message to keep connection alive.

        Args:
            connection_id: Connection ID

        Returns:
            True if sent successfully

        """
        message = WebSocketMessage(
            type=WebSocketMessageType.HEARTBEAT,
            data={"timestamp": datetime.now(timezone.utc).isoformat()},
        )
        return await self.send_message(connection_id, message)


class WebSocketAPI:
    """WebSocket API for streaming agent interactions."""

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        session_manager: SessionManager,
    ):
        """Initialize WebSocket API.

        Args:
            orchestrator: Agent orchestrator
            session_manager: Session manager

        """
        self.orchestrator = orchestrator
        self.session_manager = session_manager
        self.connection_manager = ConnectionManager()

    async def handle_connection(
        self, websocket: WebSocket, connection_id: str, session_id: str | None = None
    ) -> None:
        """Handle a WebSocket connection.

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection ID
            session_id: Optional session ID

        """
        await self.connection_manager.connect(websocket, connection_id, session_id)

        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(connection_id)
            )

            # Process messages
            while True:
                data = await websocket.receive_json()
                await self._process_message(connection_id, session_id, data)

        except WebSocketDisconnect:
            heartbeat_task.cancel()
            self.connection_manager.disconnect(connection_id, session_id)
        except Exception as e:
            # Send error message
            error_message = WebSocketMessage(
                type=WebSocketMessageType.ERROR,
                data={"error": str(e)},
            )
            await self.connection_manager.send_message(connection_id, error_message)
            self.connection_manager.disconnect(connection_id, session_id)

    async def _heartbeat_loop(self, connection_id: str, interval: int = 30) -> None:
        """Send periodic heartbeat messages.

        Args:
            connection_id: Connection ID
            interval: Heartbeat interval in seconds

        """
        try:
            while True:
                await asyncio.sleep(interval)
                await self.connection_manager.send_heartbeat(connection_id)
        except asyncio.CancelledError:
            pass

    async def _process_message(
        self, connection_id: str, session_id: str | None, data: dict[str, Any]
    ) -> None:
        """Process an incoming WebSocket message.

        Args:
            connection_id: Connection ID
            session_id: Session ID
            data: Message data

        """
        message_type = data.get("type")

        if message_type == "execute_agent":
            await self._handle_agent_execution(connection_id, session_id, data)
        elif message_type == "execute_workflow":
            await self._handle_workflow_execution(connection_id, session_id, data)
        elif message_type == "chat_message":
            await self._handle_chat_message(connection_id, session_id, data)
        else:
            # Unknown message type
            error_message = WebSocketMessage(
                type=WebSocketMessageType.ERROR,
                data={"error": f"Unknown message type: {message_type}"},
            )
            await self.connection_manager.send_message(connection_id, error_message)

    async def _handle_agent_execution(
        self, connection_id: str, session_id: str | None, data: dict[str, Any]
    ) -> None:
        """Handle agent execution request.

        Args:
            connection_id: Connection ID
            session_id: Session ID
            data: Request data

        """
        try:
            # Parse request
            agent_role = AgentRole(data["agent_role"])
            objective = data["objective"]
            context = data.get("context", {})

            # Send task start message
            task_id = f"task_{datetime.now(timezone.utc).timestamp()}"
            start_message = WebSocketMessage(
                type=WebSocketMessageType.TASK_START,
                data={
                    "task_id": task_id,
                    "agent_role": agent_role.value,
                    "objective": objective,
                },
            )
            await self.connection_manager.send_message(connection_id, start_message)

            # Create and execute task
            task = AgentTask(
                id=task_id,
                role=agent_role,
                objective=objective,
                context=context,
            )

            agent = self.orchestrator.agents.get(agent_role)
            if not agent:
                raise ValueError(f"No agent registered for role {agent_role}")

            # Execute task (with progress updates)
            result = await self._execute_task_with_progress(
                connection_id, agent, task
            )

            # Send completion message
            complete_message = WebSocketMessage(
                type=WebSocketMessageType.TASK_COMPLETE,
                data={
                    "task_id": task.id,
                    "status": result.status.value,
                    "result": result.result,
                },
            )
            await self.connection_manager.send_message(connection_id, complete_message)

        except Exception as e:
            error_message = WebSocketMessage(
                type=WebSocketMessageType.TASK_ERROR,
                data={"error": str(e)},
            )
            await self.connection_manager.send_message(connection_id, error_message)

    async def _handle_workflow_execution(
        self, connection_id: str, session_id: str | None, data: dict[str, Any]
    ) -> None:
        """Handle workflow execution request.

        Args:
            connection_id: Connection ID
            session_id: Session ID
            data: Request data

        """
        try:
            # Parse request
            name = data["name"]
            objective = data["objective"]
            stages = [WorkflowStage(s) for s in data.get("stages", [])]
            context = data.get("context", {})

            # Create workflow
            workflow = await self.orchestrator.create_workflow(
                name=name,
                objective=objective,
                stages=stages if stages else None,
                context=context,
            )

            # Send workflow start message
            start_message = WebSocketMessage(
                type=WebSocketMessageType.WORKFLOW_START,
                data={
                    "workflow_id": workflow.id,
                    "name": workflow.name,
                    "stages": [s.value for s in workflow.stages],
                },
            )
            await self.connection_manager.send_message(connection_id, start_message)

            # Execute workflow (with stage updates)
            result = await self._execute_workflow_with_progress(
                connection_id, workflow.id
            )

            # Send completion message
            complete_message = WebSocketMessage(
                type=WebSocketMessageType.WORKFLOW_COMPLETE,
                data={
                    "workflow_id": workflow.id,
                    "status": result.status.value,
                    "completed_stages": [
                        s.value for s in workflow.stages if any(
                            t.role.value == s.value and t.status == TaskStatus.COMPLETED
                            for t in result.tasks
                        )
                    ],
                },
            )
            await self.connection_manager.send_message(connection_id, complete_message)

        except Exception as e:
            error_message = WebSocketMessage(
                type=WebSocketMessageType.WORKFLOW_ERROR,
                data={"error": str(e)},
            )
            await self.connection_manager.send_message(connection_id, error_message)

    async def _handle_chat_message(
        self, connection_id: str, session_id: str | None, data: dict[str, Any]
    ) -> None:
        """Handle chat message.

        Args:
            connection_id: Connection ID
            session_id: Session ID
            data: Message data

        """
        try:
            message = data["message"]

            if not session_id:
                raise ValueError("Session ID required for chat messages")

            # Add user message to session
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")

            await session.add_message("user", message)

            # Process message and stream response
            message_id = f"msg_{datetime.now(timezone.utc).timestamp()}"

            # Simulate streaming response (in production, integrate with agent)
            response_chunks = [
                "I understand ",
                "your request. ",
                "Let me help ",
                "you with that."
            ]

            for i, chunk in enumerate(response_chunks):
                chunk_message = WebSocketMessage(
                    type=WebSocketMessageType.CHAT_CHUNK,
                    data=ChatChunkData(
                        message_id=message_id,
                        session_id=session_id,
                        chunk=chunk,
                        is_final=(i == len(response_chunks) - 1),
                    ).model_dump(),
                )
                await self.connection_manager.send_message(connection_id, chunk_message)
                await asyncio.sleep(0.1)  # Simulate streaming delay

            # Add assistant response to session
            await session.add_message("assistant", "".join(response_chunks))

        except Exception as e:
            error_message = WebSocketMessage(
                type=WebSocketMessageType.ERROR,
                data={"error": str(e)},
            )
            await self.connection_manager.send_message(connection_id, error_message)

    async def _execute_task_with_progress(
        self, connection_id: str, agent: Any, task: AgentTask
    ) -> AgentTask:
        """Execute task with progress updates.

        Args:
            connection_id: Connection ID
            agent: Agent to execute task
            task: Task to execute

        Returns:
            Completed task

        """
        # Send initial progress
        progress_message = WebSocketMessage(
            type=WebSocketMessageType.TASK_PROGRESS,
            data=TaskProgressData(
                task_id=task.id,
                status="in_progress",
                progress=0.0,
                message="Starting task execution",
            ).model_dump(),
        )
        await self.connection_manager.send_message(connection_id, progress_message)

        # Execute task
        result = await agent.process_task(task)

        # Send final progress
        final_progress = WebSocketMessage(
            type=WebSocketMessageType.TASK_PROGRESS,
            data=TaskProgressData(
                task_id=task.id,
                status=result.status.value,
                progress=1.0,
                message="Task completed",
            ).model_dump(),
        )
        await self.connection_manager.send_message(connection_id, final_progress)

        return result

    async def _execute_workflow_with_progress(
        self, connection_id: str, workflow_id: str
    ) -> Any:
        """Execute workflow with stage updates.

        Args:
            connection_id: Connection ID
            workflow_id: Workflow ID

        Returns:
            Completed workflow

        """
        # Execute workflow and send updates for each stage
        workflow = self.orchestrator.workflows[workflow_id]

        for i, stage in enumerate(workflow.stages):
            # Send stage progress
            stage_message = WebSocketMessage(
                type=WebSocketMessageType.WORKFLOW_STAGE,
                data=WorkflowProgressData(
                    workflow_id=workflow_id,
                    current_stage=stage.value,
                    completed_stages=[],
                    progress=(i + 1) / len(workflow.stages),
                    message=f"Executing stage: {stage.value}",
                ).model_dump(),
            )
            await self.connection_manager.send_message(connection_id, stage_message)

        # Execute workflow
        result = await self.orchestrator.execute_workflow(workflow_id)

        return result
