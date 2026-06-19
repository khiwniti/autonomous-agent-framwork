"""Security policies and enforcement - Phase 6."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SecurityLevel(str, Enum):
    """Security levels."""

    LOW = "low"  # Development only
    MEDIUM = "medium"  # Testing/staging
    HIGH = "high"  # Production
    CRITICAL = "critical"  # Sensitive production


class TLSVersion(str, Enum):
    """TLS protocol versions."""

    TLS_1_0 = "TLSv1.0"
    TLS_1_1 = "TLSv1.1"
    TLS_1_2 = "TLSv1.2"
    TLS_1_3 = "TLSv1.3"


class CORSPolicy(BaseModel):
    """CORS policy configuration."""

    allowed_origins: list[str] = Field(
        default=["*"],
        description="Allowed origins (* for all)",
    )
    allowed_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed HTTP methods",
    )
    allowed_headers: list[str] = Field(
        default=["*"],
        description="Allowed headers",
    )
    expose_headers: list[str] = Field(
        default_factory=list,
        description="Headers exposed to browser",
    )
    allow_credentials: bool = Field(
        default=False,
        description="Allow credentials",
    )
    max_age: int = Field(
        default=3600,
        description="Preflight cache duration (seconds)",
    )


class ContentSecurityPolicy(BaseModel):
    """Content Security Policy (CSP) configuration."""

    default_src: list[str] = Field(
        default=["'self'"],
        description="Default source for all directives",
    )
    script_src: list[str] = Field(
        default=["'self'"],
        description="Valid sources for JavaScript",
    )
    style_src: list[str] = Field(
        default=["'self'", "'unsafe-inline'"],
        description="Valid sources for CSS",
    )
    img_src: list[str] = Field(
        default=["'self'", "data:", "https:"],
        description="Valid sources for images",
    )
    connect_src: list[str] = Field(
        default=["'self'"],
        description="Valid sources for XMLHttpRequest, WebSocket",
    )
    font_src: list[str] = Field(
        default=["'self'"],
        description="Valid sources for fonts",
    )
    object_src: list[str] = Field(
        default=["'none'"],
        description="Valid sources for plugins",
    )
    frame_ancestors: list[str] = Field(
        default=["'none'"],
        description="Valid parents for embedding",
    )
    base_uri: list[str] = Field(
        default=["'self'"],
        description="Valid URIs for <base> element",
    )
    form_action: list[str] = Field(
        default=["'self'"],
        description="Valid targets for form submissions",
    )

    def to_header(self) -> str:
        """Convert CSP to HTTP header value.

        Returns:
            CSP header string

        """
        directives = []

        if self.default_src:
            directives.append(f"default-src {' '.join(self.default_src)}")
        if self.script_src:
            directives.append(f"script-src {' '.join(self.script_src)}")
        if self.style_src:
            directives.append(f"style-src {' '.join(self.style_src)}")
        if self.img_src:
            directives.append(f"img-src {' '.join(self.img_src)}")
        if self.connect_src:
            directives.append(f"connect-src {' '.join(self.connect_src)}")
        if self.font_src:
            directives.append(f"font-src {' '.join(self.font_src)}")
        if self.object_src:
            directives.append(f"object-src {' '.join(self.object_src)}")
        if self.frame_ancestors:
            directives.append(f"frame-ancestors {' '.join(self.frame_ancestors)}")
        if self.base_uri:
            directives.append(f"base-uri {' '.join(self.base_uri)}")
        if self.form_action:
            directives.append(f"form-action {' '.join(self.form_action)}")

        return "; ".join(directives)


class SecurityHeaders(BaseModel):
    """Security headers configuration."""

    strict_transport_security: str = Field(
        default="max-age=31536000; includeSubDomains",
        description="HSTS header",
    )
    x_content_type_options: str = Field(
        default="nosniff",
        description="X-Content-Type-Options header",
    )
    x_frame_options: str = Field(
        default="DENY",
        description="X-Frame-Options header",
    )
    x_xss_protection: str = Field(
        default="1; mode=block",
        description="X-XSS-Protection header",
    )
    referrer_policy: str = Field(
        default="strict-origin-when-cross-origin",
        description="Referrer-Policy header",
    )
    permissions_policy: str = Field(
        default="geolocation=(), microphone=(), camera=()",
        description="Permissions-Policy header",
    )

    def to_dict(self) -> dict[str, str]:
        """Convert headers to dictionary.

        Returns:
            Headers dictionary

        """
        return {
            "Strict-Transport-Security": self.strict_transport_security,
            "X-Content-Type-Options": self.x_content_type_options,
            "X-Frame-Options": self.x_frame_options,
            "X-XSS-Protection": self.x_xss_protection,
            "Referrer-Policy": self.referrer_policy,
            "Permissions-Policy": self.permissions_policy,
        }


class TLSConfig(BaseModel):
    """TLS/SSL configuration."""

    enabled: bool = Field(default=True, description="Enable TLS")
    min_version: TLSVersion = Field(
        default=TLSVersion.TLS_1_2,
        description="Minimum TLS version",
    )
    cert_path: str | None = Field(
        default=None,
        description="Path to TLS certificate",
    )
    key_path: str | None = Field(
        default=None,
        description="Path to TLS private key",
    )
    verify_client: bool = Field(
        default=False,
        description="Require client certificates",
    )
    ciphers: list[str] = Field(
        default_factory=lambda: [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
        ],
        description="Allowed cipher suites",
    )


class ResourceLimits(BaseModel):
    """Resource limits configuration."""

    max_concurrent_tasks: int = Field(
        default=100,
        description="Maximum concurrent tasks",
    )
    max_task_duration_seconds: int = Field(
        default=3600,
        description="Maximum task duration",
    )
    max_memory_mb: int = Field(
        default=2048,
        description="Maximum memory usage per process (MB)",
    )
    max_cpu_percent: int = Field(
        default=80,
        description="Maximum CPU usage (%)",
    )
    max_request_size_mb: int = Field(
        default=10,
        description="Maximum request size (MB)",
    )
    max_response_size_mb: int = Field(
        default=50,
        description="Maximum response size (MB)",
    )
    max_file_upload_size_mb: int = Field(
        default=100,
        description="Maximum file upload size (MB)",
    )
    max_connections: int = Field(
        default=1000,
        description="Maximum concurrent connections",
    )


class ExecutionPolicy(BaseModel):
    """Code execution policy."""

    allow_code_execution: bool = Field(
        default=True,
        description="Allow code execution",
    )
    allowed_languages: list[str] = Field(
        default_factory=lambda: ["python", "javascript", "bash"],
        description="Allowed programming languages",
    )
    enable_sandbox: bool = Field(
        default=True,
        description="Enable sandbox for code execution",
    )
    timeout_seconds: int = Field(
        default=300,
        description="Execution timeout",
    )
    max_output_size_kb: int = Field(
        default=1024,
        description="Maximum output size (KB)",
    )
    allow_network_access: bool = Field(
        default=False,
        description="Allow network access from executed code",
    )
    allow_file_system_access: bool = Field(
        default=False,
        description="Allow file system access",
    )
    allowed_imports: list[str] = Field(
        default_factory=list,
        description="Allowed imports/modules",
    )
    blocked_imports: list[str] = Field(
        default_factory=lambda: ["os", "subprocess", "sys"],
        description="Blocked imports/modules",
    )


class SecurityPolicy(BaseModel):
    """Comprehensive security policy."""

    security_level: SecurityLevel = Field(
        default=SecurityLevel.MEDIUM,
        description="Overall security level",
    )
    cors_policy: CORSPolicy = Field(
        default_factory=CORSPolicy,
        description="CORS policy",
    )
    csp: ContentSecurityPolicy = Field(
        default_factory=ContentSecurityPolicy,
        description="Content Security Policy",
    )
    security_headers: SecurityHeaders = Field(
        default_factory=SecurityHeaders,
        description="Security headers",
    )
    tls_config: TLSConfig = Field(
        default_factory=TLSConfig,
        description="TLS configuration",
    )
    resource_limits: ResourceLimits = Field(
        default_factory=ResourceLimits,
        description="Resource limits",
    )
    execution_policy: ExecutionPolicy = Field(
        default_factory=ExecutionPolicy,
        description="Code execution policy",
    )
    enable_audit_logging: bool = Field(
        default=True,
        description="Enable audit logging",
    )
    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable rate limiting",
    )
    enable_authentication: bool = Field(
        default=True,
        description="Require authentication",
    )
    enable_authorization: bool = Field(
        default=True,
        description="Enable authorization checks",
    )
    enable_input_validation: bool = Field(
        default=True,
        description="Enable input validation",
    )
    enable_output_sanitization: bool = Field(
        default=True,
        description="Enable output sanitization",
    )

    @classmethod
    def for_security_level(cls, level: SecurityLevel) -> "SecurityPolicy":
        """Create policy for security level.

        Args:
            level: Security level

        Returns:
            Security policy

        """
        if level == SecurityLevel.LOW:
            return cls(
                security_level=level,
                cors_policy=CORSPolicy(allowed_origins=["*"]),
                execution_policy=ExecutionPolicy(
                    enable_sandbox=False,
                    allow_network_access=True,
                    allow_file_system_access=True,
                ),
                enable_rate_limiting=False,
                enable_authentication=False,
            )

        elif level == SecurityLevel.MEDIUM:
            return cls(
                security_level=level,
                cors_policy=CORSPolicy(
                    allowed_origins=["http://localhost:*", "https://localhost:*"]
                ),
                execution_policy=ExecutionPolicy(
                    enable_sandbox=True,
                    allow_network_access=False,
                ),
            )

        elif level == SecurityLevel.HIGH:
            return cls(
                security_level=level,
                cors_policy=CORSPolicy(allowed_origins=[]),
                tls_config=TLSConfig(min_version=TLSVersion.TLS_1_2),
                execution_policy=ExecutionPolicy(
                    enable_sandbox=True,
                    allow_network_access=False,
                    allow_file_system_access=False,
                ),
            )

        elif level == SecurityLevel.CRITICAL:
            return cls(
                security_level=level,
                cors_policy=CORSPolicy(allowed_origins=[]),
                tls_config=TLSConfig(
                    min_version=TLSVersion.TLS_1_3,
                    verify_client=True,
                ),
                execution_policy=ExecutionPolicy(
                    allow_code_execution=False,
                ),
                resource_limits=ResourceLimits(
                    max_concurrent_tasks=50,
                    max_task_duration_seconds=1800,
                ),
            )

        return cls(security_level=level)


# Global security policy
_security_policy: SecurityPolicy | None = None


def get_security_policy() -> SecurityPolicy:
    """Get global security policy.

    Returns:
        Global security policy

    """
    global _security_policy
    if _security_policy is None:
        _security_policy = SecurityPolicy()
    return _security_policy


def set_security_policy(policy: SecurityPolicy) -> None:
    """Set global security policy.

    Args:
        policy: Security policy to set

    """
    global _security_policy
    _security_policy = policy


def initialize_security_policy(
    security_level: SecurityLevel = SecurityLevel.MEDIUM,
) -> SecurityPolicy:
    """Initialize global security policy.

    Args:
        security_level: Security level

    Returns:
        Initialized security policy

    """
    global _security_policy
    _security_policy = SecurityPolicy.for_security_level(security_level)
    return _security_policy
