"""Checkpoint and resume functionality for long-running workflows - Phase 5."""

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent.agents.base import AgentTask
from agent.core.orchestrator import Workflow
from agent.session.manager import Session


class Checkpoint(BaseModel):
    """Workflow or session checkpoint for resume."""

    id: str = Field(description="Checkpoint ID")
    type: str = Field(description="Checkpoint type (workflow, session, task)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )
    data: dict[str, Any] = Field(description="Checkpoint data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Checkpoint metadata")


class CheckpointManager:
    """Manages checkpoints for workflows and sessions."""

    def __init__(self, checkpoint_dir: str | Path = ".checkpoints"):
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints

        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    async def save_workflow_checkpoint(
        self, workflow: Workflow, metadata: dict[str, Any] | None = None
    ) -> str:
        """Save a workflow checkpoint.

        Args:
            workflow: Workflow to checkpoint
            metadata: Optional checkpoint metadata

        Returns:
            Checkpoint ID

        """
        checkpoint_id = f"workflow_{workflow.id}_{datetime.now(timezone.utc).timestamp()}"

        checkpoint = Checkpoint(
            id=checkpoint_id,
            type="workflow",
            data={
                "workflow_id": workflow.id,
                "name": workflow.name,
                "objective": workflow.objective,
                "stages": [s.value for s in workflow.stages],
                "current_stage": workflow.current_stage.value if workflow.current_stage else None,
                "status": workflow.status.value,
                "tasks": [self._serialize_task(t) for t in workflow.tasks],
                "context": workflow.context,
                "created_at": workflow.created_at.isoformat(),
                "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
                "completed_at": workflow.completed_at.isoformat()
                if workflow.completed_at
                else None,
                "error": workflow.error,
            },
            metadata=metadata or {},
        )

        # Save checkpoint to disk
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint.model_dump(), f, indent=2)

        return checkpoint_id

    async def save_session_checkpoint(
        self, session: Session, metadata: dict[str, Any] | None = None
    ) -> str:
        """Save a session checkpoint.

        Args:
            session: Session to checkpoint
            metadata: Optional checkpoint metadata

        Returns:
            Checkpoint ID

        """
        checkpoint_id = f"session_{session.id}_{datetime.now(timezone.utc).timestamp()}"

        checkpoint = Checkpoint(
            id=checkpoint_id,
            type="session",
            data={
                "session_id": session.id,
                "name": session.name,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "tasks": [self._serialize_task(t) for t in session.tasks],
                "messages": session.messages,
                "metadata": session.metadata,
                "is_active": session.is_active,
            },
            metadata=metadata or {},
        )

        # Save checkpoint to disk
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint.model_dump(), f, indent=2)

        return checkpoint_id

    async def load_workflow_checkpoint(self, checkpoint_id: str) -> Workflow | None:
        """Load a workflow from checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Workflow or None if not found

        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        if not checkpoint_path.exists():
            return None

        with open(checkpoint_path, "r") as f:
            checkpoint_data = json.load(f)

        checkpoint = Checkpoint(**checkpoint_data)

        if checkpoint.type != "workflow":
            return None

        from agent.core.orchestrator import WorkflowStage, WorkflowStatus

        # Reconstruct workflow
        data = checkpoint.data
        workflow = Workflow(
            id=data["workflow_id"],
            name=data["name"],
            objective=data["objective"],
            stages=[WorkflowStage(s) for s in data["stages"]],
            current_stage=WorkflowStage(data["current_stage"]) if data["current_stage"] else None,
            status=WorkflowStatus(data["status"]),
            tasks=[self._deserialize_task(t) for t in data["tasks"]],
            context=data["context"],
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data["started_at"] else None,
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data["completed_at"]
            else None,
            error=data["error"],
        )

        return workflow

    async def load_session_checkpoint(self, checkpoint_id: str) -> Session | None:
        """Load a session from checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Session or None if not found

        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        if not checkpoint_path.exists():
            return None

        with open(checkpoint_path, "r") as f:
            checkpoint_data = json.load(f)

        checkpoint = Checkpoint(**checkpoint_data)

        if checkpoint.type != "session":
            return None

        # Reconstruct session
        data = checkpoint.data
        session = Session(
            id=data["session_id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            tasks=[self._deserialize_task(t) for t in data["tasks"]],
            messages=data["messages"],
            metadata=data["metadata"],
            is_active=data["is_active"],
        )

        return session

    async def list_checkpoints(
        self, checkpoint_type: str | None = None
    ) -> list[Checkpoint]:
        """List all checkpoints.

        Args:
            checkpoint_type: Optional filter by type

        Returns:
            List of checkpoints

        """
        checkpoints = []

        for checkpoint_path in self.checkpoint_dir.glob("*.json"):
            with open(checkpoint_path, "r") as f:
                checkpoint_data = json.load(f)

            checkpoint = Checkpoint(**checkpoint_data)

            if checkpoint_type is None or checkpoint.type == checkpoint_type:
                checkpoints.append(checkpoint)

        # Sort by creation time (most recent first)
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)

        return checkpoints

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            True if deleted, False if not found

        """
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"

        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True

        return False

    async def cleanup_old_checkpoints(self, max_age_days: int = 30) -> int:
        """Clean up checkpoints older than max_age_days.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of checkpoints cleaned up

        """
        now = datetime.now(timezone.utc)
        deleted_count = 0

        for checkpoint_path in self.checkpoint_dir.glob("*.json"):
            with open(checkpoint_path, "r") as f:
                checkpoint_data = json.load(f)

            checkpoint = Checkpoint(**checkpoint_data)
            age = (now - checkpoint.created_at).days

            if age > max_age_days:
                checkpoint_path.unlink()
                deleted_count += 1

        return deleted_count

    def _serialize_task(self, task: AgentTask) -> dict[str, Any]:
        """Serialize a task for checkpoint.

        Args:
            task: Task to serialize

        Returns:
            Serialized task

        """
        return {
            "id": task.id,
            "role": task.role.value,
            "objective": task.objective,
            "context": task.context,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result,
            "error": task.error,
            "dependencies": task.dependencies,
        }

    def _deserialize_task(self, data: dict[str, Any]) -> AgentTask:
        """Deserialize a task from checkpoint.

        Args:
            data: Serialized task data

        Returns:
            Task

        """
        from agent.agents.base import AgentRole, TaskStatus

        return AgentTask(
            id=data["id"],
            role=AgentRole(data["role"]),
            objective=data["objective"],
            context=data["context"],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data["started_at"] else None,
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data["completed_at"]
            else None,
            result=data["result"],
            error=data["error"],
            dependencies=data["dependencies"],
        )


async def resume_workflow(
    checkpoint_manager: CheckpointManager,
    checkpoint_id: str,
    orchestrator: Any,
) -> Workflow | None:
    """Resume a workflow from checkpoint.

    Args:
        checkpoint_manager: Checkpoint manager
        checkpoint_id: Checkpoint ID
        orchestrator: Agent orchestrator

    Returns:
        Resumed workflow or None if not found

    """
    workflow = await checkpoint_manager.load_workflow_checkpoint(checkpoint_id)

    if not workflow:
        return None

    # Re-register workflow with orchestrator
    orchestrator.workflows[workflow.id] = workflow

    # Continue execution from current stage
    if workflow.status.value in ["pending", "in_progress"]:
        # Find next incomplete stage
        completed_roles = {t.role for t in workflow.tasks if t.status.value == "completed"}

        for stage in workflow.stages:
            # Map stage to role
            from agent.core.orchestrator import WorkflowStage
            from agent.agents.base import AgentRole

            role_mapping = {
                WorkflowStage.REQUIREMENTS: AgentRole.REQUIREMENTS,
                WorkflowStage.ARCHITECTURE: AgentRole.ARCHITECTURE,
                WorkflowStage.IMPLEMENTATION: AgentRole.IMPLEMENTATION,
                WorkflowStage.TESTING: AgentRole.TESTING,
                WorkflowStage.DEPLOYMENT: AgentRole.DEPLOYMENT,
                WorkflowStage.OPERATIONS: AgentRole.OPERATIONS,
            }

            if role_mapping[stage] not in completed_roles:
                workflow.current_stage = stage
                break

    return workflow
