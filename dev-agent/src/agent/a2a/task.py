"""A2A Task Lifecycle Management.

Implements the A2A task state machine:
  submitted → working → input-required → completed/failed/canceled

Tasks flow through states as agents process them, with support for:
- Streaming updates via Server-Sent Events
- Human-in-the-loop pause/resume
- Artifact collection per task
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """A2A Task lifecycle states."""
    
    SUBMITTED = "submitted"  # Task received, queued for processing
    WORKING = "working"  # Agent actively processing task
    INPUT_REQUIRED = "input-required"  # Paused, awaiting user/agent input
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Task failed with error
    CANCELED = "canceled"  # Task canceled by user/system


class PartType(str, Enum):
    """Content part types in task messages."""
    
    TEXT = "text"
    FILE = "file"
    DATA = "data"


class MessagePart(BaseModel):
    """A single part of a message (text, file, or structured data)."""
    
    type: PartType = Field(description="Part type")
    content: str | dict[str, Any] = Field(description="Part content")
    mime_type: str | None = Field(default=None, description="MIME type for files")
    name: str | None = Field(default=None, description="Optional name/filename")


class TaskMessage(BaseModel):
    """A message in the task conversation."""
    
    role: str = Field(description="Message role: 'user' or 'agent'")
    parts: list[MessagePart] = Field(default=[], description="Message content parts")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def user_text(cls, text: str) -> "TaskMessage":
        """Create a user text message."""
        return cls(
            role="user",
            parts=[MessagePart(type=PartType.TEXT, content=text)],
        )
    
    @classmethod
    def agent_text(cls, text: str) -> "TaskMessage":
        """Create an agent text message."""
        return cls(
            role="agent",
            parts=[MessagePart(type=PartType.TEXT, content=text)],
        )


class Artifact(BaseModel):
    """An artifact produced by the task."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Artifact name")
    type: str = Field(description="Artifact type (e.g., 'prd', 'code', 'test-report')")
    content: str | dict[str, Any] = Field(description="Artifact content")
    mime_type: str = Field(default="text/plain", description="MIME type")
    created_at: datetime = Field(default_factory=datetime.now)


class TaskState(BaseModel):
    """
    Complete state for an A2A task.
    
    This represents the full task lifecycle including messages,
    artifacts, and metadata.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Task ID")
    session_id: str | None = Field(default=None, description="Session ID for multi-turn")
    
    # Status tracking
    status: TaskStatus = Field(default=TaskStatus.SUBMITTED)
    status_message: str | None = Field(default=None, description="Human-readable status")
    
    # Conversation history
    messages: list[TaskMessage] = Field(default=[], description="Task messages")
    
    # Produced artifacts
    artifacts: list[Artifact] = Field(default=[], description="Task artifacts")
    
    # Error handling
    error: str | None = Field(default=None, description="Error message if failed")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = Field(default=None)
    
    # Agent tracking
    agent_id: str | None = Field(default=None, description="Processing agent ID")
    skill_id: str | None = Field(default=None, description="Skill being used")
    
    def update_status(self, status: TaskStatus, message: str | None = None) -> None:
        """Update task status with timestamp."""
        self.status = status
        self.status_message = message
        self.updated_at = datetime.now()
        
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED):
            self.completed_at = datetime.now()
    
    def add_message(self, message: TaskMessage) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def add_artifact(self, artifact: Artifact) -> None:
        """Add an artifact to the task."""
        self.artifacts.append(artifact)
        self.updated_at = datetime.now()
    
    def get_text_content(self) -> str:
        """Extract all text content from messages."""
        texts = []
        for msg in self.messages:
            for part in msg.parts:
                if part.type == PartType.TEXT:
                    texts.append(f"{msg.role}: {part.content}")
        return "\n".join(texts)


class StreamEvent(BaseModel):
    """Server-Sent Event for task streaming."""
    
    event: str = Field(description="Event type")
    data: dict[str, Any] = Field(description="Event data")
    
    def to_sse(self) -> str:
        """Format as SSE string."""
        import json
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class TaskManager:
    """
    Manages A2A task lifecycle.
    
    Provides:
    - Task creation and persistence
    - Status updates with streaming
    - Artifact collection
    - Session management for multi-turn conversations
    
    Usage:
        manager = TaskManager()
        task = await manager.create_task("Analyze requirements")
        await manager.update_status(task.id, TaskStatus.WORKING)
        await manager.add_artifact(task.id, artifact)
        await manager.complete_task(task.id)
    """
    
    def __init__(self, persistence_backend: Any | None = None):
        """
        Initialize TaskManager.
        
        Args:
            persistence_backend: Optional storage backend (e.g., PostgreSQL)
        """
        self._tasks: dict[str, TaskState] = {}
        self._sessions: dict[str, list[str]] = {}  # session_id -> task_ids
        self._streams: dict[str, list[asyncio.Queue]] = {}  # task_id -> subscriber queues
        self._persistence = persistence_backend
    
    async def create_task(
        self,
        initial_message: str,
        session_id: str | None = None,
        agent_id: str | None = None,
        skill_id: str | None = None,
    ) -> TaskState:
        """
        Create a new task.
        
        Args:
            initial_message: Initial task description/request
            session_id: Optional session for multi-turn conversations
            agent_id: Target agent ID
            skill_id: Target skill ID
            
        Returns:
            New TaskState
        """
        task = TaskState(
            session_id=session_id or str(uuid.uuid4()),
            agent_id=agent_id,
            skill_id=skill_id,
        )
        
        task.add_message(TaskMessage.user_text(initial_message))
        
        self._tasks[task.id] = task
        
        # Track in session
        if task.session_id not in self._sessions:
            self._sessions[task.session_id] = []
        self._sessions[task.session_id].append(task.id)
        
        # Persist if backend configured
        if self._persistence:
            await self._persist_task(task)
        
        return task
    
    async def get_task(self, task_id: str) -> TaskState | None:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    async def get_session_tasks(self, session_id: str) -> list[TaskState]:
        """Get all tasks in a session."""
        task_ids = self._sessions.get(session_id, [])
        return [self._tasks[tid] for tid in task_ids if tid in self._tasks]
    
    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str | None = None,
    ) -> TaskState | None:
        """
        Update task status and notify subscribers.
        
        Args:
            task_id: Task ID
            status: New status
            message: Optional status message
            
        Returns:
            Updated TaskState or None if not found
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        task.update_status(status, message)
        
        # Emit streaming event
        await self._emit_event(task_id, StreamEvent(
            event="status",
            data={
                "task_id": task_id,
                "status": status.value,
                "message": message,
                "timestamp": task.updated_at.isoformat(),
            },
        ))
        
        # Persist
        if self._persistence:
            await self._persist_task(task)
        
        return task
    
    async def add_message(
        self,
        task_id: str,
        role: str,
        content: str,
    ) -> TaskState | None:
        """Add a message to the task conversation."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        msg = TaskMessage(
            role=role,
            parts=[MessagePart(type=PartType.TEXT, content=content)],
        )
        task.add_message(msg)
        
        # Emit streaming event
        await self._emit_event(task_id, StreamEvent(
            event="message",
            data={
                "task_id": task_id,
                "role": role,
                "content": content,
                "timestamp": msg.timestamp.isoformat(),
            },
        ))
        
        return task
    
    async def add_artifact(
        self,
        task_id: str,
        artifact: Artifact,
    ) -> TaskState | None:
        """Add an artifact to the task."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        task.add_artifact(artifact)
        
        # Emit streaming event
        await self._emit_event(task_id, StreamEvent(
            event="artifact",
            data={
                "task_id": task_id,
                "artifact_id": artifact.id,
                "artifact_name": artifact.name,
                "artifact_type": artifact.type,
            },
        ))
        
        return task
    
    async def complete_task(
        self,
        task_id: str,
        final_message: str | None = None,
    ) -> TaskState | None:
        """Mark task as completed."""
        task = await self.update_status(task_id, TaskStatus.COMPLETED, final_message)
        
        if task and final_message:
            await self.add_message(task_id, "agent", final_message)
        
        # Emit completion event
        await self._emit_event(task_id, StreamEvent(
            event="complete",
            data={
                "task_id": task_id,
                "status": TaskStatus.COMPLETED.value,
                "artifacts_count": len(task.artifacts) if task else 0,
            },
        ))
        
        return task
    
    async def fail_task(
        self,
        task_id: str,
        error: str,
    ) -> TaskState | None:
        """Mark task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.error = error
        
        task = await self.update_status(task_id, TaskStatus.FAILED, error)
        
        await self._emit_event(task_id, StreamEvent(
            event="error",
            data={
                "task_id": task_id,
                "error": error,
            },
        ))
        
        return task
    
    async def request_input(
        self,
        task_id: str,
        prompt: str,
    ) -> TaskState | None:
        """
        Pause task and request user input (human-in-the-loop).
        
        Args:
            task_id: Task ID
            prompt: Prompt to show user
            
        Returns:
            Updated TaskState
        """
        task = await self.update_status(
            task_id,
            TaskStatus.INPUT_REQUIRED,
            prompt,
        )
        
        await self._emit_event(task_id, StreamEvent(
            event="input_required",
            data={
                "task_id": task_id,
                "prompt": prompt,
            },
        ))
        
        return task
    
    async def provide_input(
        self,
        task_id: str,
        user_input: str,
    ) -> TaskState | None:
        """
        Resume a paused task with user input.
        
        Args:
            task_id: Task ID
            user_input: User's response
            
        Returns:
            Updated TaskState (back to WORKING status)
        """
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.INPUT_REQUIRED:
            return None
        
        await self.add_message(task_id, "user", user_input)
        return await self.update_status(task_id, TaskStatus.WORKING, "Resuming with input")
    
    # ========================================================================
    # Streaming support
    # ========================================================================
    
    async def subscribe(self, task_id: str) -> AsyncIterator[StreamEvent]:
        """
        Subscribe to task events via SSE.
        
        Usage:
            async for event in manager.subscribe(task_id):
                yield event.to_sse()
        """
        # Create subscriber queue
        if task_id not in self._streams:
            self._streams[task_id] = []
        
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
        self._streams[task_id].append(queue)
        
        try:
            # Send initial state
            task = self._tasks.get(task_id)
            if task:
                yield StreamEvent(
                    event="init",
                    data=task.model_dump(mode="json"),
                )
            
            # Stream updates
            while True:
                event = await queue.get()
                if event is None:  # Termination signal
                    break
                yield event
        finally:
            # Cleanup subscription
            if task_id in self._streams:
                self._streams[task_id].remove(queue)
    
    async def _emit_event(self, task_id: str, event: StreamEvent) -> None:
        """Emit event to all subscribers."""
        if task_id in self._streams:
            for queue in self._streams[task_id]:
                await queue.put(event)
    
    async def _persist_task(self, task: TaskState) -> None:
        """Persist task to backend storage."""
        if self._persistence and hasattr(self._persistence, "save"):
            await self._persistence.save(task.id, task.model_dump(mode="json"))
