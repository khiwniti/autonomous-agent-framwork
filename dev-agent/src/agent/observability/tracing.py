"""OpenTelemetry distributed tracing - Phase 6."""

import contextvars
from datetime import datetime, timezone
from typing import Any, Callable
from functools import wraps

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


# Context variable for trace context
trace_context = contextvars.ContextVar("trace_context", default=None)


class TracingManager:
    """Manages distributed tracing with OpenTelemetry."""

    def __init__(
        self,
        service_name: str = "autonomous-agent",
        otlp_endpoint: str | None = None,
        console_export: bool = False,
    ):
        """Initialize tracing manager.

        Args:
            service_name: Service name for traces
            otlp_endpoint: OTLP collector endpoint (e.g., "localhost:4317")
            console_export: Enable console exporter for debugging

        """
        self.service_name = service_name
        self.otlp_endpoint = otlp_endpoint

        # Create resource
        resource = Resource(attributes={SERVICE_NAME: service_name})

        # Create tracer provider
        self.provider = TracerProvider(resource=resource)

        # Add span processors
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            self.provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        if console_export:
            console_exporter = ConsoleSpanExporter()
            self.provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(self.provider)

        # Create tracer
        self.tracer = trace.get_tracer(__name__)

        # Propagator for distributed context
        self.propagator = TraceContextTextMapPropagator()

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    ) -> Span:
        """Start a new span.

        Args:
            name: Span name
            attributes: Span attributes
            kind: Span kind

        Returns:
            Started span

        """
        span = self.tracer.start_span(name, kind=kind)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        return span

    def end_span(
        self, span: Span, status: StatusCode = StatusCode.OK, error: Exception | None = None
    ) -> None:
        """End a span.

        Args:
            span: Span to end
            status: Span status
            error: Optional error

        """
        if error:
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.record_exception(error)
        else:
            span.set_status(Status(status))

        span.end()

    def extract_context(self, carrier: dict[str, str]) -> Any:
        """Extract trace context from carrier.

        Args:
            carrier: Context carrier (e.g., HTTP headers)

        Returns:
            Trace context

        """
        return self.propagator.extract(carrier)

    def inject_context(self, carrier: dict[str, str]) -> None:
        """Inject trace context into carrier.

        Args:
            carrier: Context carrier (e.g., HTTP headers)

        """
        self.propagator.inject(carrier)

    def shutdown(self) -> None:
        """Shutdown tracing provider."""
        self.provider.shutdown()


# Decorators for automatic tracing


def trace_function(
    span_name: str | None = None,
    attributes: dict[str, Any] | None = None,
    capture_args: bool = False,
    capture_result: bool = False,
):
    """Decorator to trace function execution.

    Args:
        span_name: Optional custom span name (defaults to function name)
        attributes: Static attributes to add to span
        capture_args: Capture function arguments as attributes
        capture_result: Capture return value as attribute

    Returns:
        Decorated function

    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(name) as span:
                # Add static attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Capture function arguments
                if capture_args:
                    for i, arg in enumerate(args):
                        span.set_attribute(f"arg.{i}", str(arg))
                    for key, value in kwargs.items():
                        span.set_attribute(f"kwarg.{key}", str(value))

                try:
                    result = func(*args, **kwargs)

                    # Capture result
                    if capture_result:
                        span.set_attribute("result", str(result))

                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(name) as span:
                # Add static attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Capture function arguments
                if capture_args:
                    for i, arg in enumerate(args):
                        span.set_attribute(f"arg.{i}", str(arg))
                    for key, value in kwargs.items():
                        span.set_attribute(f"kwarg.{key}", str(value))

                try:
                    result = await func(*args, **kwargs)

                    # Capture result
                    if capture_result:
                        span.set_attribute("result", str(result))

                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def trace_agent_task(func: Callable) -> Callable:
    """Decorator to trace agent task execution.

    Args:
        func: Function to decorate

    Returns:
        Decorated function

    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        tracer = trace.get_tracer(__name__)

        # Extract task info from arguments
        task = args[1] if len(args) > 1 else kwargs.get("task")

        span_name = f"agent.task.{task.role.value if task else 'unknown'}"

        with tracer.start_as_current_span(span_name, kind=trace.SpanKind.INTERNAL) as span:
            if task:
                span.set_attribute("task.id", task.id)
                span.set_attribute("task.role", task.role.value)
                span.set_attribute("task.objective", task.objective)
                span.set_attribute("task.status", task.status.value)

            try:
                result = await func(*args, **kwargs)

                if task:
                    span.set_attribute("task.final_status", result.status.value)

                span.set_status(Status(StatusCode.OK))
                return result

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper


def trace_workflow_execution(func: Callable) -> Callable:
    """Decorator to trace workflow execution.

    Args:
        func: Function to decorate

    Returns:
        Decorated function

    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        tracer = trace.get_tracer(__name__)

        # Extract workflow info
        workflow_id = args[1] if len(args) > 1 else kwargs.get("workflow_id")

        with tracer.start_as_current_span(
            "workflow.execute", kind=trace.SpanKind.INTERNAL
        ) as span:
            span.set_attribute("workflow.id", str(workflow_id))

            try:
                result = await func(*args, **kwargs)

                span.set_attribute("workflow.status", result.status.value)
                span.set_attribute("workflow.stages_count", len(result.stages))
                span.set_attribute("workflow.tasks_count", len(result.tasks))

                span.set_status(Status(StatusCode.OK))
                return result

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper


def trace_llm_request(func: Callable) -> Callable:
    """Decorator to trace LLM requests.

    Args:
        func: Function to decorate

    Returns:
        Decorated function

    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("llm.request", kind=trace.SpanKind.CLIENT) as span:
            # Extract request info
            messages = kwargs.get("messages", [])
            model = kwargs.get("model", "unknown")

            span.set_attribute("llm.model", model)
            span.set_attribute("llm.messages_count", len(messages))

            # Calculate prompt size
            prompt_size = sum(len(m.get("content", "")) for m in messages)
            span.set_attribute("llm.prompt_size", prompt_size)

            start_time = datetime.now(timezone.utc)

            try:
                result = await func(*args, **kwargs)

                # Record response info
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                span.set_attribute("llm.duration_seconds", duration)

                if hasattr(result, "content"):
                    span.set_attribute("llm.response_size", len(result.content))

                span.set_status(Status(StatusCode.OK))
                return result

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper


def trace_tool_execution(func: Callable) -> Callable:
    """Decorator to trace tool execution.

    Args:
        func: Function to decorate

    Returns:
        Decorated function

    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        tracer = trace.get_tracer(__name__)

        tool_name = self.__class__.__name__ if hasattr(self, "__class__") else "unknown"

        with tracer.start_as_current_span(
            f"tool.{tool_name}", kind=trace.SpanKind.INTERNAL
        ) as span:
            span.set_attribute("tool.name", tool_name)

            # Capture tool parameters
            if args:
                span.set_attribute("tool.args_count", len(args))
            if kwargs:
                for key, value in kwargs.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"tool.param.{key}", value)

            try:
                result = await func(self, *args, **kwargs)

                if result:
                    span.set_attribute("tool.result_type", type(result).__name__)

                span.set_status(Status(StatusCode.OK))
                return result

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper


# Global tracing manager
_tracing_manager: TracingManager | None = None


def get_tracing_manager() -> TracingManager:
    """Get global tracing manager.

    Returns:
        Global tracing manager

    """
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager()
    return _tracing_manager


def initialize_tracing(
    service_name: str = "autonomous-agent",
    otlp_endpoint: str | None = None,
    console_export: bool = False,
) -> TracingManager:
    """Initialize global tracing manager.

    Args:
        service_name: Service name
        otlp_endpoint: OTLP collector endpoint
        console_export: Enable console export

    Returns:
        Initialized tracing manager

    """
    global _tracing_manager
    _tracing_manager = TracingManager(service_name, otlp_endpoint, console_export)
    return _tracing_manager


def shutdown_tracing() -> None:
    """Shutdown global tracing manager."""
    global _tracing_manager
    if _tracing_manager:
        _tracing_manager.shutdown()
        _tracing_manager = None
