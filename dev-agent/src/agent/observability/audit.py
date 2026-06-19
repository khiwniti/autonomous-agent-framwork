"""Audit logging system - Phase 6."""

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent.observability.logging import get_logger


class AuditEventType(str, Enum):
    """Audit event types."""

    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_CREATED = "auth.token_created"
    AUTH_TOKEN_REVOKED = "auth.token_revoked"
    AUTH_FAILED = "auth.failed"

    # Authorization events
    AUTHZ_ACCESS_GRANTED = "authz.access_granted"
    AUTHZ_ACCESS_DENIED = "authz.access_denied"
    AUTHZ_PERMISSION_CHANGED = "authz.permission_changed"

    # Data access events
    DATA_READ = "data.read"
    DATA_CREATE = "data.create"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"

    # System events
    SYSTEM_CONFIG_CHANGED = "system.config_changed"
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"

    # Agent events
    AGENT_TASK_CREATED = "agent.task_created"
    AGENT_TASK_COMPLETED = "agent.task_completed"
    AGENT_TASK_FAILED = "agent.task_failed"

    # Workflow events
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_EXECUTED = "workflow.executed"
    WORKFLOW_FAILED = "workflow.failed"

    # Security events
    SECURITY_RATE_LIMIT_HIT = "security.rate_limit_hit"
    SECURITY_QUOTA_EXCEEDED = "security.quota_exceeded"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    SECURITY_POLICY_VIOLATION = "security.policy_violation"

    # Session events
    SESSION_CREATED = "session.created"
    SESSION_TERMINATED = "session.terminated"

    # Admin events
    ADMIN_USER_CREATED = "admin.user_created"
    ADMIN_USER_DELETED = "admin.user_deleted"
    ADMIN_ROLE_CHANGED = "admin.role_changed"


class AuditSeverity(str, Enum):
    """Audit event severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """Audit event model."""

    event_id: str = Field(description="Unique event ID")
    event_type: AuditEventType = Field(description="Event type")
    timestamp: datetime = Field(description="Event timestamp")
    severity: AuditSeverity = Field(description="Event severity")

    # Actor information
    user_id: str | None = Field(default=None, description="User ID")
    session_id: str | None = Field(default=None, description="Session ID")
    ip_address: str | None = Field(default=None, description="IP address")
    user_agent: str | None = Field(default=None, description="User agent")

    # Event details
    resource_type: str | None = Field(default=None, description="Resource type")
    resource_id: str | None = Field(default=None, description="Resource ID")
    action: str = Field(description="Action performed")
    outcome: str = Field(description="Action outcome (success/failure)")

    # Additional context
    details: dict[str, Any] = Field(default_factory=dict, description="Event details")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")

    # Correlation
    correlation_id: str | None = Field(default=None, description="Correlation ID")
    parent_event_id: str | None = Field(default=None, description="Parent event ID")


class AuditLogger:
    """Audit logging manager."""

    def __init__(
        self,
        audit_log_file: str | Path | None = None,
        enable_console: bool = False,
        retention_days: int = 90,
    ):
        """Initialize audit logger.

        Args:
            audit_log_file: Path to audit log file
            enable_console: Enable console output
            retention_days: Audit log retention period

        """
        self.audit_log_file = Path(audit_log_file) if audit_log_file else None
        self.enable_console = enable_console
        self.retention_days = retention_days

        # Create audit log directory
        if self.audit_log_file:
            self.audit_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Get structured logger
        self.logger = get_logger("audit")

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        outcome: str,
        severity: AuditSeverity = AuditSeverity.LOW,
        user_id: str | None = None,
        session_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Log audit event.

        Args:
            event_type: Event type
            action: Action performed
            outcome: Action outcome
            severity: Event severity
            user_id: User ID
            session_id: Session ID
            resource_type: Resource type
            resource_id: Resource ID
            ip_address: IP address
            user_agent: User agent
            details: Event details
            metadata: Additional metadata
            correlation_id: Correlation ID

        Returns:
            Created audit event

        """
        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            details=details or {},
            metadata=metadata or {},
            correlation_id=correlation_id,
        )

        # Write to audit log file
        if self.audit_log_file:
            self._write_to_file(event)

        # Log to console if enabled
        if self.enable_console:
            self._log_to_console(event)

        return event

    def _write_to_file(self, event: AuditEvent) -> None:
        """Write event to audit log file.

        Args:
            event: Audit event

        """
        with open(self.audit_log_file, "a") as f:
            f.write(event.model_dump_json() + "\n")

    def _log_to_console(self, event: AuditEvent) -> None:
        """Log event to console.

        Args:
            event: Audit event

        """
        self.logger.info(
            f"AUDIT: {event.event_type.value}",
            event_id=event.event_id,
            action=event.action,
            outcome=event.outcome,
            severity=event.severity.value,
            user_id=event.user_id,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            **event.details,
        )

    # Convenience methods for common audit events

    def log_authentication(
        self,
        user_id: str,
        outcome: str,
        auth_method: str,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log authentication event.

        Args:
            user_id: User ID
            outcome: Authentication outcome
            auth_method: Authentication method
            ip_address: IP address
            details: Additional details

        Returns:
            Audit event

        """
        event_type = (
            AuditEventType.AUTH_LOGIN
            if outcome == "success"
            else AuditEventType.AUTH_FAILED
        )
        severity = AuditSeverity.MEDIUM if outcome == "failure" else AuditSeverity.LOW

        return self.log_event(
            event_type=event_type,
            action=f"authentication via {auth_method}",
            outcome=outcome,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            details=details or {},
        )

    def log_authorization(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log authorization event.

        Args:
            user_id: User ID
            resource_type: Resource type
            resource_id: Resource ID
            action: Action attempted
            outcome: Authorization outcome
            details: Additional details

        Returns:
            Audit event

        """
        event_type = (
            AuditEventType.AUTHZ_ACCESS_GRANTED
            if outcome == "success"
            else AuditEventType.AUTHZ_ACCESS_DENIED
        )
        severity = AuditSeverity.HIGH if outcome == "failure" else AuditSeverity.LOW

        return self.log_event(
            event_type=event_type,
            action=f"{action} {resource_type}",
            outcome=outcome,
            severity=severity,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )

    def log_data_access(
        self,
        user_id: str,
        operation: str,
        resource_type: str,
        resource_id: str,
        outcome: str,
        session_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log data access event.

        Args:
            user_id: User ID
            operation: Operation (read/create/update/delete)
            resource_type: Resource type
            resource_id: Resource ID
            outcome: Operation outcome
            session_id: Session ID
            details: Additional details

        Returns:
            Audit event

        """
        event_type_map = {
            "read": AuditEventType.DATA_READ,
            "create": AuditEventType.DATA_CREATE,
            "update": AuditEventType.DATA_UPDATE,
            "delete": AuditEventType.DATA_DELETE,
            "export": AuditEventType.DATA_EXPORT,
        }

        event_type = event_type_map.get(operation.lower(), AuditEventType.DATA_READ)
        severity = AuditSeverity.MEDIUM if operation == "delete" else AuditSeverity.LOW

        return self.log_event(
            event_type=event_type,
            action=f"{operation} {resource_type}",
            outcome=outcome,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        action: str,
        severity: AuditSeverity,
        user_id: str | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log security event.

        Args:
            event_type: Event type
            action: Action/event description
            severity: Event severity
            user_id: User ID
            ip_address: IP address
            details: Additional details

        Returns:
            Audit event

        """
        return self.log_event(
            event_type=event_type,
            action=action,
            outcome="detected",
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            details=details or {},
        )

    def log_agent_task(
        self,
        task_id: str,
        agent_role: str,
        action: str,
        outcome: str,
        user_id: str | None = None,
        session_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log agent task event.

        Args:
            task_id: Task ID
            agent_role: Agent role
            action: Action (created/completed/failed)
            outcome: Task outcome
            user_id: User ID
            session_id: Session ID
            details: Additional details

        Returns:
            Audit event

        """
        event_type_map = {
            "created": AuditEventType.AGENT_TASK_CREATED,
            "completed": AuditEventType.AGENT_TASK_COMPLETED,
            "failed": AuditEventType.AGENT_TASK_FAILED,
        }

        event_type = event_type_map.get(
            action.lower(), AuditEventType.AGENT_TASK_CREATED
        )
        severity = AuditSeverity.LOW

        return self.log_event(
            event_type=event_type,
            action=f"agent task {action}",
            outcome=outcome,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            resource_type="agent_task",
            resource_id=task_id,
            details={**(details if details is not None else {}), "agent_role": agent_role},
        )

    def log_workflow_event(
        self,
        workflow_id: str,
        workflow_name: str,
        action: str,
        outcome: str,
        user_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log workflow event.

        Args:
            workflow_id: Workflow ID
            workflow_name: Workflow name
            action: Action (created/executed/failed)
            outcome: Workflow outcome
            user_id: User ID
            details: Additional details

        Returns:
            Audit event

        """
        event_type_map = {
            "created": AuditEventType.WORKFLOW_CREATED,
            "executed": AuditEventType.WORKFLOW_EXECUTED,
            "failed": AuditEventType.WORKFLOW_FAILED,
        }

        event_type = event_type_map.get(action.lower(), AuditEventType.WORKFLOW_CREATED)
        severity = AuditSeverity.MEDIUM if action == "failed" else AuditSeverity.LOW

        return self.log_event(
            event_type=event_type,
            action=f"workflow {action}",
            outcome=outcome,
            severity=severity,
            user_id=user_id,
            resource_type="workflow",
            resource_id=workflow_id,
            details={**(details if details is not None else {}), "workflow_name": workflow_name},
        )

    def query_events(
        self,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        severity: AuditSeverity | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events.

        Args:
            event_types: Filter by event types
            user_id: Filter by user ID
            start_time: Filter by start time
            end_time: Filter by end time
            severity: Filter by severity
            limit: Maximum number of events to return

        Returns:
            List of matching audit events

        """
        if not self.audit_log_file or not self.audit_log_file.exists():
            return []

        events = []

        with open(self.audit_log_file, "r") as f:
            for line in f:
                try:
                    event_data = json.loads(line.strip())
                    event = AuditEvent.model_validate(event_data)

                    # Apply filters
                    if event_types and event.event_type not in event_types:
                        continue
                    if user_id and event.user_id != user_id:
                        continue
                    if start_time and event.timestamp < start_time:
                        continue
                    if end_time and event.timestamp > end_time:
                        continue
                    if severity and event.severity != severity:
                        continue

                    events.append(event)

                    if len(events) >= limit:
                        break

                except Exception:
                    continue

        return events


# Global audit logger
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger.

    Returns:
        Global audit logger instance

    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(
            audit_log_file="logs/audit.log", enable_console=True
        )
    return _audit_logger


def initialize_audit_logger(
    audit_log_file: str | Path,
    enable_console: bool = False,
    retention_days: int = 90,
) -> AuditLogger:
    """Initialize global audit logger.

    Args:
        audit_log_file: Path to audit log file
        enable_console: Enable console output
        retention_days: Audit log retention period

    Returns:
        Initialized audit logger

    """
    global _audit_logger
    _audit_logger = AuditLogger(audit_log_file, enable_console, retention_days)
    return _audit_logger
