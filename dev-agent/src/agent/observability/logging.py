"""Structured logging with correlation IDs - Phase 6."""

import contextvars
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars


# Context variable for correlation ID
correlation_id_context = contextvars.ContextVar("correlation_id", default=None)
request_id_context = contextvars.ContextVar("request_id", default=None)
session_id_context = contextvars.ContextVar("session_id", default=None)
user_id_context = contextvars.ContextVar("user_id", default=None)


def generate_correlation_id() -> str:
    """Generate unique correlation ID.

    Returns:
        UUID-based correlation ID

    """
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in context.

    Args:
        correlation_id: Correlation ID to set

    """
    correlation_id_context.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get correlation ID from context.

    Returns:
        Current correlation ID or None

    """
    return correlation_id_context.get()


def set_request_id(request_id: str) -> None:
    """Set request ID in context.

    Args:
        request_id: Request ID to set

    """
    request_id_context.set(request_id)


def get_request_id() -> str | None:
    """Get request ID from context.

    Returns:
        Current request ID or None

    """
    return request_id_context.get()


def set_session_id(session_id: str) -> None:
    """Set session ID in context.

    Args:
        session_id: Session ID to set

    """
    session_id_context.set(session_id)


def get_session_id() -> str | None:
    """Get session ID from context.

    Returns:
        Current session ID or None

    """
    return session_id_context.get()


def set_user_id(user_id: str) -> None:
    """Set user ID in context.

    Args:
        user_id: User ID to set

    """
    user_id_context.set(user_id)


def get_user_id() -> str | None:
    """Get user ID from context.

    Returns:
        Current user ID or None

    """
    return user_id_context.get()


def add_correlation_id(logger, method_name, event_dict):
    """Add correlation ID to log events.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary

    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id

    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id

    session_id = get_session_id()
    if session_id:
        event_dict["session_id"] = session_id

    user_id = get_user_id()
    if user_id:
        event_dict["user_id"] = user_id

    return event_dict


def add_timestamp(logger, method_name, event_dict):
    """Add ISO timestamp to log events.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary

    """
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_log_level(logger, method_name, event_dict):
    """Add log level to event dict.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary

    """
    event_dict["level"] = method_name.upper()
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    log_file: str | Path | None = None,
    json_output: bool = False,
    console_output: bool = True,
) -> None:
    """Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        json_output: Output JSON format
        console_output: Output to console

    """
    # Convert log level string to constant
    level = getattr(logging, log_level.upper())

    # Configure standard logging to pass through to structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Processors for structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        add_timestamp,
        add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # JSON renderer for production
        renderer = structlog.processors.JSONRenderer()
    else:
        # Console renderer for development
        renderer = structlog.dev.ConsoleRenderer(colors=console_output)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)

        formatter = structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )
        file_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str | None = None) -> Any:
    """Get structured logger.

    Args:
        name: Logger name (defaults to caller's module)

    Returns:
        Structured logger instance

    """
    return structlog.get_logger(name)


class LoggerContextManager:
    """Context manager for logging with automatic correlation ID."""

    def __init__(
        self,
        logger: Any,
        correlation_id: str | None = None,
        **context: Any,
    ):
        """Initialize context manager.

        Args:
            logger: Logger instance
            correlation_id: Optional correlation ID (generates if None)
            **context: Additional context to bind

        """
        self.logger = logger
        self.correlation_id = correlation_id or generate_correlation_id()
        self.context = context
        self.old_correlation_id = None

    def __enter__(self):
        """Enter context."""
        self.old_correlation_id = get_correlation_id()
        set_correlation_id(self.correlation_id)

        # Bind context
        bound_logger = self.logger.bind(**self.context)
        return bound_logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        # Restore old correlation ID
        if self.old_correlation_id:
            set_correlation_id(self.old_correlation_id)
        else:
            correlation_id_context.set(None)

        return False


def log_execution(
    operation: str,
    log_args: bool = False,
    log_result: bool = False,
):
    """Decorator to log function execution.

    Args:
        operation: Operation name
        log_args: Log function arguments
        log_result: Log function result

    Returns:
        Decorated function

    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger()

            correlation_id = get_correlation_id() or generate_correlation_id()
            set_correlation_id(correlation_id)

            log_context = {
                "operation": operation,
                "function": func.__name__,
                "module": func.__module__,
            }

            if log_args:
                log_context["args"] = str(args)
                log_context["kwargs"] = str(kwargs)

            logger.info(f"{operation} started", **log_context)

            try:
                start_time = datetime.now(timezone.utc)
                result = await func(*args, **kwargs)
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

                log_context["duration_seconds"] = duration

                if log_result and result:
                    log_context["result"] = str(result)[:200]  # Truncate

                logger.info(f"{operation} completed", **log_context)
                return result

            except Exception as e:
                logger.error(
                    f"{operation} failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    **log_context,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger()

            correlation_id = get_correlation_id() or generate_correlation_id()
            set_correlation_id(correlation_id)

            log_context = {
                "operation": operation,
                "function": func.__name__,
                "module": func.__module__,
            }

            if log_args:
                log_context["args"] = str(args)
                log_context["kwargs"] = str(kwargs)

            logger.info(f"{operation} started", **log_context)

            try:
                start_time = datetime.now(timezone.utc)
                result = func(*args, **kwargs)
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

                log_context["duration_seconds"] = duration

                if log_result and result:
                    log_context["result"] = str(result)[:200]

                logger.info(f"{operation} completed", **log_context)
                return result

            except Exception as e:
                logger.error(
                    f"{operation} failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    **log_context,
                )
                raise

        # Return appropriate wrapper
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Convenience logger instances
logger = get_logger()


def log_agent_task(task_id: str, agent_role: str, objective: str, status: str) -> None:
    """Log agent task event.

    Args:
        task_id: Task ID
        agent_role: Agent role
        objective: Task objective
        status: Task status

    """
    logger.info(
        "agent task",
        task_id=task_id,
        agent_role=agent_role,
        objective=objective,
        status=status,
    )


def log_workflow_event(
    workflow_id: str, name: str, stage: str | None = None, status: str | None = None
) -> None:
    """Log workflow event.

    Args:
        workflow_id: Workflow ID
        name: Workflow name
        stage: Current stage
        status: Workflow status

    """
    logger.info(
        "workflow event",
        workflow_id=workflow_id,
        name=name,
        stage=stage,
        status=status,
    )


def log_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
    user_id: str | None = None,
) -> None:
    """Log API request.

    Args:
        method: HTTP method
        endpoint: API endpoint
        status_code: HTTP status code
        duration: Request duration
        user_id: Optional user ID

    """
    logger.info(
        "api request",
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration_seconds=duration,
        user_id=user_id,
    )


def log_security_event(
    event_type: str,
    details: dict[str, Any],
    severity: str = "info",
) -> None:
    """Log security event.

    Args:
        event_type: Event type
        details: Event details
        severity: Event severity

    """
    log_method = getattr(logger, severity.lower())
    log_method("security event", event_type=event_type, **details)
