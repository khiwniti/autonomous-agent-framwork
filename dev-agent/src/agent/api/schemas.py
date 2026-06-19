"""Pydantic schemas for API request/response models - Phase 5."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# Request Models


class AgentExecutionRequest(BaseModel):
    """Request to execute an agent task."""

    agent_role: str = Field(description="Agent role (requirements, architecture, etc.)")
    objective: str = Field(description="Task objective")
    context: dict[str, Any] = Field(default_factory=dict, description="Task context")
    session_id: str | None = Field(default=None, description="Optional session ID")


class WorkflowExecutionRequest(BaseModel):
    """Request to execute a workflow."""

    name: str = Field(description="Workflow name")
    objective: str = Field(description="Overall workflow objective")
    stages: list[str] = Field(
        default_factory=list, description="Workflow stages (empty = full SDLC)"
    )
    context: dict[str, Any] = Field(default_factory=dict, description="Initial context")
    session_id: str | None = Field(default=None, description="Optional session ID")


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""

    name: str | None = Field(default=None, description="Optional session name")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session metadata")


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(description="User message")
    session_id: str = Field(description="Session ID")
    stream: bool = Field(default=False, description="Enable streaming response")


# Response Models


class TaskStatusResponse(BaseModel):
    """Task execution status."""

    task_id: str = Field(description="Task ID")
    status: str = Field(description="Task status")
    agent_role: str = Field(description="Agent role")
    objective: str = Field(description="Task objective")
    started_at: datetime | None = Field(default=None, description="Start timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    error: str | None = Field(default=None, description="Error message if failed")
    result: dict[str, Any] | None = Field(default=None, description="Task result")


class WorkflowStatusResponse(BaseModel):
    """Workflow execution status."""

    workflow_id: str = Field(description="Workflow ID")
    name: str = Field(description="Workflow name")
    status: str = Field(description="Workflow status")
    current_stage: str | None = Field(default=None, description="Current stage")
    completed_stages: list[str] = Field(
        default_factory=list, description="Completed stages"
    )
    failed_stages: list[str] = Field(default_factory=list, description="Failed stages")
    progress: float = Field(description="Progress percentage (0-1)")
    error: str | None = Field(default=None, description="Error message if failed")


class SessionResponse(BaseModel):
    """Session information."""

    session_id: str = Field(description="Session ID")
    name: str | None = Field(default=None, description="Session name")
    created_at: datetime = Field(description="Creation timestamp")
    last_activity: datetime = Field(description="Last activity timestamp")
    task_count: int = Field(description="Number of tasks")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session metadata")


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    message_id: str = Field(description="Message ID")
    session_id: str = Field(description="Session ID")
    role: Literal["user", "assistant", "system"] = Field(description="Message role")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(description="Message timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Message metadata")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    details: dict[str, Any] | None = Field(default=None, description="Error details")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Service health status"
    )
    version: str = Field(description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
    components: dict[str, str] = Field(
        default_factory=dict, description="Component health status"
    )


# WebSocket Message Models


class WebSocketMessageType(str, Enum):
    """WebSocket message types."""

    TASK_START = "task_start"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_STAGE = "workflow_stage"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_ERROR = "workflow_error"
    CHAT_MESSAGE = "chat_message"
    CHAT_CHUNK = "chat_chunk"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class WebSocketMessage(BaseModel):
    """WebSocket message."""

    type: WebSocketMessageType = Field(description="Message type")
    data: dict[str, Any] = Field(description="Message data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )


class TaskProgressData(BaseModel):
    """Task progress data for WebSocket."""

    task_id: str = Field(description="Task ID")
    status: str = Field(description="Current status")
    progress: float = Field(description="Progress percentage (0-1)")
    message: str | None = Field(default=None, description="Progress message")
    iteration: int | None = Field(default=None, description="Current iteration")


class WorkflowProgressData(BaseModel):
    """Workflow progress data for WebSocket."""

    workflow_id: str = Field(description="Workflow ID")
    current_stage: str = Field(description="Current stage")
    completed_stages: list[str] = Field(description="Completed stages")
    progress: float = Field(description="Overall progress (0-1)")
    message: str | None = Field(default=None, description="Progress message")


class ChatChunkData(BaseModel):
    """Chat streaming chunk data."""

    message_id: str = Field(description="Message ID")
    session_id: str = Field(description="Session ID")
    chunk: str = Field(description="Text chunk")
    is_final: bool = Field(default=False, description="Is this the final chunk")


# Pagination Models


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: list[Any] = Field(description="Items in this page")
    total: int = Field(description="Total items")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total pages")


# Rate Limiting Models


class RateLimitInfo(BaseModel):
    """Rate limit information."""

    limit: int = Field(description="Request limit per window")
    remaining: int = Field(description="Remaining requests")
    reset: datetime = Field(description="When the limit resets")
    window_seconds: int = Field(description="Window duration in seconds")


class QuotaInfo(BaseModel):
    """Quota information."""

    total: int = Field(description="Total quota")
    used: int = Field(description="Used quota")
    remaining: int = Field(description="Remaining quota")
    period: str = Field(description="Quota period (daily, monthly, etc.)")
    reset: datetime = Field(description="When the quota resets")
