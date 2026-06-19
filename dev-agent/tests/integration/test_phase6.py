"""Integration tests for Phase 6: Observability & Security."""

import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from agent.agents.base import AgentRole, TaskStatus
from agent.core.orchestrator import WorkflowStatus
from agent.observability.audit import (
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    initialize_audit_logger,
)
from agent.observability.logging import (
    configure_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    generate_correlation_id,
    log_execution,
)
from agent.observability.metrics import AgentMetrics, get_metrics, reset_metrics
from agent.observability.resources import ResourceMonitor, ResourceType
from agent.observability.tracing import (
    TracingManager,
    trace_function,
    initialize_tracing,
)
from agent.security.authentication import AuthManager
from agent.security.policies import (
    SecurityPolicy,
    SecurityLevel,
    get_security_policy,
    initialize_security_policy,
)
from agent.security.rate_limiting import RateLimiter, QuotaManager
from agent.security.secrets import (
    SecretsManager,
    SecretType,
    SecretBackend,
    initialize_secrets_manager,
)
from agent.security.validation import (
    InputValidator,
    SanitizationMode,
    ValidationError,
    validate_input,
)


# Metrics Tests


class TestMetrics:
    """Test Prometheus metrics collection."""

    def test_agent_metrics_creation(self):
        """Test creating metrics collector."""
        metrics = AgentMetrics()
        assert metrics is not None
        assert metrics.agent_tasks_total is not None
        assert metrics.workflows_total is not None

    def test_record_task_execution(self):
        """Test recording task execution."""
        reset_metrics()
        metrics = get_metrics()

        metrics.record_task_execution(
            AgentRole.REQUIREMENTS, TaskStatus.COMPLETED, 1.5
        )

        # Metrics should be recorded
        assert metrics.agent_tasks_total is not None

    def test_record_workflow_execution(self):
        """Test recording workflow execution."""
        reset_metrics()
        metrics = get_metrics()

        metrics.record_workflow_execution("test-workflow", WorkflowStatus.COMPLETED, 10.0)

        assert metrics.workflows_total is not None

    def test_record_api_request(self):
        """Test recording API request."""
        reset_metrics()
        metrics = get_metrics()

        metrics.record_api_request("GET", "/api/test", 200, 0.05, 100, 500)

        assert metrics.api_requests_total is not None

    def test_export_metrics(self):
        """Test exporting metrics."""
        reset_metrics()
        metrics = get_metrics()

        metrics.record_task_execution(AgentRole.REQUIREMENTS, TaskStatus.COMPLETED, 1.0)

        exported = metrics.export_metrics()
        assert isinstance(exported, bytes)
        assert b"agent_tasks_total" in exported


# Tracing Tests


class TestTracing:
    """Test OpenTelemetry distributed tracing."""

    def test_tracing_manager_creation(self):
        """Test creating tracing manager."""
        manager = TracingManager(console_export=True)
        assert manager is not None
        assert manager.tracer is not None

    def test_start_span(self):
        """Test starting a span."""
        manager = TracingManager(console_export=False)
        span = manager.start_span(
            "test-operation", attributes={"key": "value"}
        )

        assert span is not None
        manager.end_span(span)

    def test_trace_decorator(self):
        """Test trace decorator."""

        @trace_function(span_name="test_func", capture_args=True)
        def test_func(x: int, y: int) -> int:
            return x + y

        result = test_func(1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_trace_async_decorator(self):
        """Test trace decorator on async function."""

        @trace_function(span_name="async_test", capture_result=True)
        async def async_test_func(value: str) -> str:
            await asyncio.sleep(0.01)
            return value.upper()

        result = await async_test_func("hello")
        assert result == "HELLO"


# Logging Tests


class TestLogging:
    """Test structured logging."""

    def test_configure_logging(self):
        """Test logging configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            configure_logging(log_level="INFO", log_file=log_file, json_output=True)

            logger = get_logger("test")
            logger.info("test message", key="value")

            assert log_file.exists()

    def test_correlation_id(self):
        """Test correlation ID management."""
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)

        retrieved = get_correlation_id()
        assert retrieved == correlation_id

    def test_log_execution_decorator(self):
        """Test log execution decorator."""

        @log_execution("test_operation", log_args=True, log_result=True)
        def test_operation(x: int) -> int:
            return x * 2

        result = test_operation(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_log_execution_async(self):
        """Test log execution decorator on async function."""

        @log_execution("async_operation")
        async def async_operation(value: str) -> str:
            await asyncio.sleep(0.01)
            return f"processed_{value}"

        result = await async_operation("test")
        assert result == "processed_test"


# Audit Logging Tests


class TestAuditLogging:
    """Test audit logging."""

    def test_audit_logger_creation(self):
        """Test creating audit logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / "audit.log"
            logger = AuditLogger(audit_log_file=audit_file)

            assert logger is not None

    def test_log_authentication_event(self):
        """Test logging authentication event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / "audit.log"
            logger = AuditLogger(audit_log_file=audit_file)

            event = logger.log_authentication(
                user_id="user123",
                outcome="success",
                auth_method="api_key",
                ip_address="192.168.1.1",
            )

            assert event.event_type == AuditEventType.AUTH_LOGIN
            assert event.user_id == "user123"
            assert audit_file.exists()

    def test_log_data_access(self):
        """Test logging data access event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / "audit.log"
            logger = AuditLogger(audit_log_file=audit_file)

            event = logger.log_data_access(
                user_id="user123",
                operation="read",
                resource_type="secret",
                resource_id="my_secret",
                outcome="success",
            )

            assert event.event_type == AuditEventType.DATA_READ
            assert event.resource_id == "my_secret"

    def test_query_events(self):
        """Test querying audit events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_file = Path(tmpdir) / "audit.log"
            logger = AuditLogger(audit_log_file=audit_file)

            # Log some events
            logger.log_authentication("user1", "success", "api_key")
            logger.log_authentication("user2", "failure", "password")

            # Query events
            events = logger.query_events(
                event_types=[AuditEventType.AUTH_LOGIN, AuditEventType.AUTH_FAILED]
            )

            assert len(events) == 2


# Input Validation Tests


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_sanitize_string(self):
        """Test string sanitization."""
        result = InputValidator.sanitize_string(
            "<script>alert('xss')</script>",
            mode=SanitizationMode.ESCAPE,
        )

        assert "script" in result
        assert "<" not in result  # Should be escaped

    def test_validate_alphanumeric(self):
        """Test alphanumeric validation."""
        result = InputValidator.validate_alphanumeric("abc123")
        assert result == "abc123"

        with pytest.raises(ValidationError):
            InputValidator.validate_alphanumeric("abc-123")

    def test_validate_email(self):
        """Test email validation."""
        result = InputValidator.validate_email("user@example.com")
        assert result == "user@example.com"

        with pytest.raises(ValidationError):
            InputValidator.validate_email("invalid-email")

    def test_validate_url(self):
        """Test URL validation."""
        result = InputValidator.validate_url("https://example.com")
        assert result == "https://example.com"

        with pytest.raises(ValidationError):
            InputValidator.validate_url("javascript:alert(1)")

    def test_validate_path(self):
        """Test path validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Valid path
            result = InputValidator.validate_path("subdir/file.txt", base_path=base_path)
            assert result is not None

            # Path traversal attempt
            with pytest.raises(ValidationError):
                InputValidator.validate_path("../../../etc/passwd", base_path=base_path)

    def test_validate_integer(self):
        """Test integer validation."""
        result = InputValidator.validate_integer("42", min_value=0, max_value=100)
        assert result == 42

        with pytest.raises(ValidationError):
            InputValidator.validate_integer("200", max_value=100)

    def test_sql_injection_detection(self):
        """Test SQL injection detection."""
        with pytest.raises(ValidationError):
            InputValidator.sanitize_string(
                "admin' OR '1'='1", mode=SanitizationMode.STRICT
            )

    def test_xss_detection(self):
        """Test XSS detection."""
        with pytest.raises(ValidationError):
            InputValidator.sanitize_string(
                "<img src=x onerror=alert(1)>", mode=SanitizationMode.STRICT
            )


# Secrets Management Tests


class TestSecretsManagement:
    """Test secrets management."""

    def test_secrets_manager_creation(self):
        """Test creating secrets manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            secrets_file = Path(tmpdir) / "secrets.json"
            manager = SecretsManager(
                backend=SecretBackend.FILE,
                secrets_file=secrets_file,
                master_password="test_password",
            )

            assert manager is not None

    def test_set_and_get_secret(self):
        """Test setting and getting secret."""
        manager = SecretsManager(backend=SecretBackend.MEMORY)

        manager.set_secret("api_key", "secret_value_123", SecretType.API_KEY)
        retrieved = manager.get_secret("api_key")

        assert retrieved == "secret_value_123"

    def test_secret_expiration(self):
        """Test secret expiration."""
        manager = SecretsManager(backend=SecretBackend.MEMORY)

        manager.set_secret(
            "temp_secret",
            "value",
            expires_in_days=-1,  # Already expired
        )

        retrieved = manager.get_secret("temp_secret")
        assert retrieved is None  # Should be expired

    def test_delete_secret(self):
        """Test deleting secret."""
        manager = SecretsManager(backend=SecretBackend.MEMORY)

        manager.set_secret("delete_me", "value")
        assert manager.get_secret("delete_me") == "value"

        manager.delete_secret("delete_me")
        assert manager.get_secret("delete_me") is None

    def test_rotate_secret(self):
        """Test rotating secret."""
        manager = SecretsManager(backend=SecretBackend.MEMORY)

        manager.set_secret("rotate_me", "old_value", rotation_enabled=True)
        manager.rotate_secret("rotate_me", "new_value")

        assert manager.get_secret("rotate_me") == "new_value"

    def test_list_secrets(self):
        """Test listing secrets."""
        manager = SecretsManager(backend=SecretBackend.MEMORY)

        manager.set_secret("secret1", "value1", SecretType.API_KEY)
        manager.set_secret("secret2", "value2", SecretType.PASSWORD)

        secrets = manager.list_secrets()
        assert len(secrets) == 2


# Security Policies Tests


class TestSecurityPolicies:
    """Test security policies."""

    def test_security_policy_creation(self):
        """Test creating security policy."""
        policy = SecurityPolicy()
        assert policy is not None
        assert policy.security_level == SecurityLevel.MEDIUM

    def test_security_level_policies(self):
        """Test different security level policies."""
        # Low security
        low = SecurityPolicy.for_security_level(SecurityLevel.LOW)
        assert low.enable_authentication is False

        # High security
        high = SecurityPolicy.for_security_level(SecurityLevel.HIGH)
        assert high.tls_config.min_version.value == "TLSv1.2"
        assert high.execution_policy.allow_file_system_access is False

        # Critical security
        critical = SecurityPolicy.for_security_level(SecurityLevel.CRITICAL)
        assert critical.execution_policy.allow_code_execution is False

    def test_csp_header_generation(self):
        """Test CSP header generation."""
        policy = SecurityPolicy()
        csp_header = policy.csp.to_header()

        assert "default-src" in csp_header
        assert "script-src" in csp_header

    def test_security_headers(self):
        """Test security headers."""
        policy = SecurityPolicy()
        headers = policy.security_headers.to_dict()

        assert "Strict-Transport-Security" in headers
        assert "X-Content-Type-Options" in headers


# Resource Monitoring Tests


class TestResourceMonitoring:
    """Test resource monitoring and limits."""

    def test_resource_monitor_creation(self):
        """Test creating resource monitor."""
        monitor = ResourceMonitor(
            cpu_limit_percent=80.0,
            memory_limit_mb=1024.0,
            max_concurrent_tasks=10,
        )

        assert monitor is not None

    def test_get_current_usage(self):
        """Test getting current resource usage."""
        monitor = ResourceMonitor()
        usage = monitor.get_current_usage()

        assert usage.cpu_percent >= 0
        assert usage.memory_mb > 0
        assert usage.active_tasks >= 0

    def test_check_limits(self):
        """Test checking resource limits."""
        monitor = ResourceMonitor(cpu_limit_percent=1.0, memory_limit_mb=1.0)
        limits = monitor.check_limits()

        # With very low limits, should exceed
        assert limits["cpu"] or limits["memory"]

    @pytest.mark.asyncio
    async def test_acquire_release_task_slot(self):
        """Test acquiring and releasing task slots."""
        monitor = ResourceMonitor(max_concurrent_tasks=2)

        # Acquire slots
        acquired1 = await monitor.acquire_task_slot(timeout=1.0)
        assert acquired1 is True
        assert monitor.active_tasks == 1

        acquired2 = await monitor.acquire_task_slot(timeout=1.0)
        assert acquired2 is True
        assert monitor.active_tasks == 2

        # Release slot
        monitor.release_task_slot()
        assert monitor.active_tasks == 1

    def test_set_and_consume_quota(self):
        """Test setting and consuming quotas."""
        monitor = ResourceMonitor()

        monitor.set_quota("user1", ResourceType.REQUESTS, 100.0)

        # Consume quota
        success, error = monitor.consume_quota("user1", ResourceType.REQUESTS, 50.0)
        assert success is True

        # Check status
        status = monitor.get_quota_status("user1", ResourceType.REQUESTS)
        assert status["used"] == 50.0
        assert status["remaining"] == 50.0

    def test_quota_exceeded(self):
        """Test quota exceeded."""
        monitor = ResourceMonitor()

        monitor.set_quota("user1", ResourceType.REQUESTS, 10.0)
        monitor.consume_quota("user1", ResourceType.REQUESTS, 10.0)

        # Should fail
        success, error = monitor.consume_quota("user1", ResourceType.REQUESTS, 1.0)
        assert success is False
        assert "exceeded" in error


# End-to-End Tests


class TestEndToEndObservability:
    """Test end-to-end observability."""

    @pytest.mark.asyncio
    async def test_complete_observability_stack(self):
        """Test complete observability stack integration."""
        # Initialize all components
        with tempfile.TemporaryDirectory() as tmpdir:
            # Metrics
            reset_metrics()
            metrics = get_metrics()

            # Tracing
            tracing = initialize_tracing(console_export=True)

            # Logging
            log_file = Path(tmpdir) / "test.log"
            configure_logging(log_file=log_file)

            # Audit
            audit_file = Path(tmpdir) / "audit.log"
            audit_logger = initialize_audit_logger(audit_file)

            # Simulate operation
            correlation_id = generate_correlation_id()
            set_correlation_id(correlation_id)

            # Record metrics
            metrics.record_task_execution(
                AgentRole.REQUIREMENTS, TaskStatus.COMPLETED, 1.0
            )

            # Log event
            logger = get_logger()
            logger.info("test operation", correlation_id=correlation_id)

            # Audit event
            audit_logger.log_authentication("user1", "success", "api_key")

            # Verify files created
            assert log_file.exists()
            assert audit_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
