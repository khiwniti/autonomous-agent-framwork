"""Prometheus metrics collection - Phase 6."""

from typing import Any, Callable

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from agent.agents.base import AgentRole, TaskStatus
from agent.core.orchestrator import WorkflowStatus


class AgentMetrics:
    """Prometheus metrics for autonomous agent system."""

    def __init__(self, registry: CollectorRegistry | None = None):
        """Initialize metrics.

        Args:
            registry: Optional custom registry

        """
        self.registry = registry or CollectorRegistry()

        # Agent execution metrics
        self.agent_tasks_total = Counter(
            "agent_tasks_total",
            "Total number of agent tasks",
            ["agent_role", "status"],
            registry=self.registry,
        )

        self.agent_task_duration = Histogram(
            "agent_task_duration_seconds",
            "Agent task execution duration",
            ["agent_role"],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
            registry=self.registry,
        )

        self.agent_task_errors = Counter(
            "agent_task_errors_total",
            "Total number of agent task errors",
            ["agent_role", "error_type"],
            registry=self.registry,
        )

        # Workflow metrics
        self.workflows_total = Counter(
            "workflows_total",
            "Total number of workflows",
            ["status"],
            registry=self.registry,
        )

        self.workflow_duration = Histogram(
            "workflow_duration_seconds",
            "Workflow execution duration",
            ["name"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0],
            registry=self.registry,
        )

        self.workflow_stages_total = Counter(
            "workflow_stages_total",
            "Total number of workflow stages executed",
            ["stage", "status"],
            registry=self.registry,
        )

        # API metrics
        self.api_requests_total = Counter(
            "api_requests_total",
            "Total number of API requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        self.api_request_duration = Histogram(
            "api_request_duration_seconds",
            "API request duration",
            ["method", "endpoint"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry,
        )

        self.api_request_size = Summary(
            "api_request_size_bytes",
            "API request size",
            ["method", "endpoint"],
            registry=self.registry,
        )

        self.api_response_size = Summary(
            "api_response_size_bytes",
            "API response size",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # WebSocket metrics
        self.websocket_connections_active = Gauge(
            "websocket_connections_active",
            "Active WebSocket connections",
            registry=self.registry,
        )

        self.websocket_messages_total = Counter(
            "websocket_messages_total",
            "Total WebSocket messages",
            ["message_type", "direction"],
            registry=self.registry,
        )

        self.websocket_connection_duration = Histogram(
            "websocket_connection_duration_seconds",
            "WebSocket connection duration",
            buckets=[1.0, 10.0, 60.0, 300.0, 600.0, 1800.0],
            registry=self.registry,
        )

        # Session metrics
        self.sessions_total = Counter(
            "sessions_total",
            "Total number of sessions",
            ["status"],
            registry=self.registry,
        )

        self.sessions_active = Gauge(
            "sessions_active",
            "Active sessions",
            registry=self.registry,
        )

        self.session_duration = Histogram(
            "session_duration_seconds",
            "Session duration",
            buckets=[60.0, 300.0, 600.0, 1800.0, 3600.0, 7200.0],
            registry=self.registry,
        )

        self.session_tasks_total = Counter(
            "session_tasks_total",
            "Total tasks per session",
            ["session_id"],
            registry=self.registry,
        )

        # Memory metrics
        self.memory_entries_total = Gauge(
            "memory_entries_total",
            "Total memory entries",
            ["memory_type"],
            registry=self.registry,
        )

        self.memory_retrieval_duration = Histogram(
            "memory_retrieval_duration_seconds",
            "Memory retrieval duration",
            ["memory_type"],
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry,
        )

        self.memory_size_bytes = Gauge(
            "memory_size_bytes",
            "Memory storage size",
            ["memory_type"],
            registry=self.registry,
        )

        # LLM metrics
        self.llm_requests_total = Counter(
            "llm_requests_total",
            "Total LLM requests",
            ["provider", "model"],
            registry=self.registry,
        )

        self.llm_request_duration = Histogram(
            "llm_request_duration_seconds",
            "LLM request duration",
            ["provider", "model"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        self.llm_tokens_used = Counter(
            "llm_tokens_used_total",
            "Total tokens used",
            ["provider", "model", "token_type"],
            registry=self.registry,
        )

        self.llm_cost = Counter(
            "llm_cost_usd_total",
            "Total LLM cost in USD",
            ["provider", "model"],
            registry=self.registry,
        )

        # Tool execution metrics
        self.tool_executions_total = Counter(
            "tool_executions_total",
            "Total tool executions",
            ["tool_name", "status"],
            registry=self.registry,
        )

        self.tool_execution_duration = Histogram(
            "tool_execution_duration_seconds",
            "Tool execution duration",
            ["tool_name"],
            buckets=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        # Checkpoint metrics
        self.checkpoints_total = Counter(
            "checkpoints_total",
            "Total checkpoints created",
            ["checkpoint_type"],
            registry=self.registry,
        )

        self.checkpoint_save_duration = Histogram(
            "checkpoint_save_duration_seconds",
            "Checkpoint save duration",
            ["checkpoint_type"],
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0],
            registry=self.registry,
        )

        self.checkpoint_load_duration = Histogram(
            "checkpoint_load_duration_seconds",
            "Checkpoint load duration",
            ["checkpoint_type"],
            buckets=[0.001, 0.01, 0.1, 0.5, 1.0],
            registry=self.registry,
        )

        # Rate limiting metrics
        self.rate_limit_hits_total = Counter(
            "rate_limit_hits_total",
            "Total rate limit hits",
            ["key_type"],
            registry=self.registry,
        )

        self.quota_exceeded_total = Counter(
            "quota_exceeded_total",
            "Total quota exceeded events",
            ["period"],
            registry=self.registry,
        )

        # Authentication metrics
        self.auth_attempts_total = Counter(
            "auth_attempts_total",
            "Total authentication attempts",
            ["auth_type", "status"],
            registry=self.registry,
        )

        self.auth_tokens_active = Gauge(
            "auth_tokens_active",
            "Active authentication tokens",
            ["token_type"],
            registry=self.registry,
        )

    # Agent metrics methods

    def record_task_execution(
        self, agent_role: AgentRole, status: TaskStatus, duration: float
    ) -> None:
        """Record agent task execution.

        Args:
            agent_role: Agent role
            status: Task status
            duration: Execution duration in seconds

        """
        self.agent_tasks_total.labels(
            agent_role=agent_role.value, status=status.value
        ).inc()
        self.agent_task_duration.labels(agent_role=agent_role.value).observe(duration)

    def record_task_error(
        self, agent_role: AgentRole, error_type: str
    ) -> None:
        """Record agent task error.

        Args:
            agent_role: Agent role
            error_type: Error type

        """
        self.agent_task_errors.labels(
            agent_role=agent_role.value, error_type=error_type
        ).inc()

    # Workflow metrics methods

    def record_workflow_execution(
        self, name: str, status: WorkflowStatus, duration: float
    ) -> None:
        """Record workflow execution.

        Args:
            name: Workflow name
            status: Workflow status
            duration: Execution duration in seconds

        """
        self.workflows_total.labels(status=status.value).inc()
        self.workflow_duration.labels(name=name).observe(duration)

    def record_workflow_stage(
        self, stage: str, status: TaskStatus
    ) -> None:
        """Record workflow stage execution.

        Args:
            stage: Stage name
            status: Stage status

        """
        self.workflow_stages_total.labels(stage=stage, status=status.value).inc()

    # API metrics methods

    def record_api_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0,
    ) -> None:
        """Record API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            status_code: HTTP status code
            duration: Request duration in seconds
            request_size: Request size in bytes
            response_size: Response size in bytes

        """
        self.api_requests_total.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).inc()
        self.api_request_duration.labels(method=method, endpoint=endpoint).observe(
            duration
        )

        if request_size > 0:
            self.api_request_size.labels(method=method, endpoint=endpoint).observe(
                request_size
            )

        if response_size > 0:
            self.api_response_size.labels(method=method, endpoint=endpoint).observe(
                response_size
            )

    # WebSocket metrics methods

    def record_websocket_connection(self, connected: bool) -> None:
        """Record WebSocket connection change.

        Args:
            connected: True if connected, False if disconnected

        """
        if connected:
            self.websocket_connections_active.inc()
        else:
            self.websocket_connections_active.dec()

    def record_websocket_message(self, message_type: str, direction: str) -> None:
        """Record WebSocket message.

        Args:
            message_type: Message type
            direction: Message direction (inbound/outbound)

        """
        self.websocket_messages_total.labels(
            message_type=message_type, direction=direction
        ).inc()

    # Session metrics methods

    def record_session_created(self) -> None:
        """Record session creation."""
        self.sessions_total.labels(status="created").inc()
        self.sessions_active.inc()

    def record_session_closed(self, duration: float) -> None:
        """Record session closure.

        Args:
            duration: Session duration in seconds

        """
        self.sessions_total.labels(status="closed").inc()
        self.sessions_active.dec()
        self.session_duration.observe(duration)

    # LLM metrics methods

    def record_llm_request(
        self,
        provider: str,
        model: str,
        duration: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float = 0.0,
    ) -> None:
        """Record LLM request.

        Args:
            provider: LLM provider
            model: Model name
            duration: Request duration
            prompt_tokens: Prompt tokens used
            completion_tokens: Completion tokens used
            cost: Request cost in USD

        """
        self.llm_requests_total.labels(provider=provider, model=model).inc()
        self.llm_request_duration.labels(provider=provider, model=model).observe(
            duration
        )
        self.llm_tokens_used.labels(
            provider=provider, model=model, token_type="prompt"
        ).inc(prompt_tokens)
        self.llm_tokens_used.labels(
            provider=provider, model=model, token_type="completion"
        ).inc(completion_tokens)

        if cost > 0:
            self.llm_cost.labels(provider=provider, model=model).inc(cost)

    # Tool metrics methods

    def record_tool_execution(
        self, tool_name: str, status: str, duration: float
    ) -> None:
        """Record tool execution.

        Args:
            tool_name: Tool name
            status: Execution status
            duration: Execution duration

        """
        self.tool_executions_total.labels(tool_name=tool_name, status=status).inc()
        self.tool_execution_duration.labels(tool_name=tool_name).observe(duration)

    # Export methods

    def export_metrics(self) -> bytes:
        """Export metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format

        """
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get Prometheus content type.

        Returns:
            Content type string

        """
        return CONTENT_TYPE_LATEST


# Global metrics instance
_metrics: AgentMetrics | None = None


def get_metrics() -> AgentMetrics:
    """Get global metrics instance.

    Returns:
        Global metrics instance

    """
    global _metrics
    if _metrics is None:
        _metrics = AgentMetrics()
    return _metrics


def reset_metrics() -> None:
    """Reset global metrics instance."""
    global _metrics
    _metrics = None
