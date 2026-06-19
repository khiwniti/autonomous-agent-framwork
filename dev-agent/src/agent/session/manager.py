"""Session management for API - Phase 5."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agent.agents.base import AgentTask


class Session(BaseModel):
    """User session with conversation history and task tracking."""

    id: str = Field(description="Unique session ID")
    name: str | None = Field(default=None, description="Optional session name")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Last activity timestamp"
    )
    tasks: list[AgentTask] = Field(default_factory=list, description="Tasks in this session")
    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Chat messages"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session metadata")
    is_active: bool = Field(default=True, description="Session active status")

    class Config:
        arbitrary_types_allowed = True

    async def add_task(self, task: AgentTask) -> None:
        """Add a task to the session.

        Args:
            task: Task to add

        """
        self.tasks.append(task)
        self.last_activity = datetime.now(timezone.utc)

    async def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a message to the session.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional message metadata

        """
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {},
            }
        )
        self.last_activity = datetime.now(timezone.utc)

    async def get_recent_messages(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages.

        Args:
            limit: Maximum messages to return

        Returns:
            Recent messages

        """
        return self.messages[-limit:]

    async def get_task_summary(self) -> dict[str, Any]:
        """Get summary of tasks in session.

        Returns:
            Task summary statistics

        """
        from agent.agents.base import TaskStatus

        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        in_progress = sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)
        pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)

        return {
            "total": len(self.tasks),
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": pending,
            "success_rate": completed / len(self.tasks) if self.tasks else 0.0,
        }


class SessionManager:
    """Manages user sessions and their lifecycle."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self.sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self, name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> Session:
        """Create a new session.

        Args:
            name: Optional session name
            metadata: Optional session metadata

        Returns:
            Created session

        """
        async with self._lock:
            session_id = f"session_{datetime.now(timezone.utc).timestamp()}"

            session = Session(
                id=session_id,
                name=name,
                metadata=metadata or {},
            )

            self.sessions[session_id] = session
            return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None if not found

        """
        return self.sessions.get(session_id)

    async def list_sessions(
        self, page: int = 1, page_size: int = 20, active_only: bool = False
    ) -> list[Session]:
        """List sessions with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            active_only: Only return active sessions

        Returns:
            List of sessions

        """
        sessions = list(self.sessions.values())

        if active_only:
            sessions = [s for s in sessions if s.is_active]

        # Sort by last activity (most recent first)
        sessions.sort(key=lambda s: s.last_activity, reverse=True)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        return sessions[start:end]

    async def count_sessions(self, active_only: bool = False) -> int:
        """Count total sessions.

        Args:
            active_only: Only count active sessions

        Returns:
            Session count

        """
        if active_only:
            return sum(1 for s in self.sessions.values() if s.is_active)
        return len(self.sessions)

    async def update_session(
        self, session_id: str, name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> Session | None:
        """Update session information.

        Args:
            session_id: Session ID
            name: New name (optional)
            metadata: New metadata (optional)

        Returns:
            Updated session or None if not found

        """
        session = await self.get_session(session_id)
        if not session:
            return None

        if name is not None:
            session.name = name

        if metadata is not None:
            session.metadata.update(metadata)

        session.last_activity = datetime.now(timezone.utc)
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found

        """
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False

    async def deactivate_session(self, session_id: str) -> bool:
        """Deactivate a session without deleting it.

        Args:
            session_id: Session ID

        Returns:
            True if deactivated, False if not found

        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.is_active = False
        session.last_activity = datetime.now(timezone.utc)
        return True

    async def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up inactive sessions older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of sessions cleaned up

        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            to_delete = []

            for session_id, session in self.sessions.items():
                age = (now - session.last_activity).total_seconds() / 3600
                if not session.is_active and age > max_age_hours:
                    to_delete.append(session_id)

            for session_id in to_delete:
                del self.sessions[session_id]

            return len(to_delete)

    async def get_session_statistics(self) -> dict[str, Any]:
        """Get overall session statistics.

        Returns:
            Session statistics

        """
        total = len(self.sessions)
        active = sum(1 for s in self.sessions.values() if s.is_active)

        total_tasks = sum(len(s.tasks) for s in self.sessions.values())
        total_messages = sum(len(s.messages) for s in self.sessions.values())

        return {
            "total_sessions": total,
            "active_sessions": active,
            "inactive_sessions": total - active,
            "total_tasks": total_tasks,
            "total_messages": total_messages,
            "avg_tasks_per_session": total_tasks / total if total > 0 else 0,
            "avg_messages_per_session": total_messages / total if total > 0 else 0,
        }
