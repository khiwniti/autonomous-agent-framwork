"""Application settings and configuration management using Pydantic."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGENT_",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Autonomous Dev Agent"
    version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = Field(default=False, description="Enable debug mode")

    # LLM Configuration
    llm_provider: Literal["openai", "ollama", "vllm"] = Field(
        default="openai", description="LLM provider to use"
    )
    llm_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible API",
    )
    llm_api_key: str | None = Field(default=None, description="API key for LLM service")
    llm_model: str = Field(default="gpt-4-turbo-preview", description="Default model to use")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    llm_max_tokens: int = Field(default=4096, ge=1, description="Max tokens for completion")
    llm_timeout: int = Field(default=60, ge=1, description="Request timeout in seconds")

    # Token Budget Management
    token_max_context: int = Field(
        default=128000, description="Maximum context window size in tokens"
    )
    token_max_messages: int = Field(
        default=20, description="Maximum messages in sliding window"
    )
    token_summarization_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Context usage threshold for summarization"
    )

    # Memory Configuration
    memory_backend: Literal["redis", "in-memory"] = Field(
        default="in-memory", description="Memory storage backend"
    )
    memory_ttl: int = Field(default=3600, description="Memory TTL in seconds")
    redis_url: str | None = Field(default=None, description="Redis connection URL")

    # Agent Configuration
    agent_max_iterations: int = Field(
        default=25, ge=1, le=100, description="Max ReAct loop iterations"
    )
    agent_reflection_interval: int = Field(
        default=5, ge=1, description="Reflection interval in iterations"
    )
    agent_enable_checkpoints: bool = Field(
        default=True, description="Enable checkpoint/resume functionality"
    )

    # Tool Configuration
    tool_execution_timeout: int = Field(
        default=300, ge=1, description="Tool execution timeout in seconds"
    )
    tool_max_retries: int = Field(default=3, ge=0, description="Max retries for failed tool calls")

    # Sandbox Configuration
    sandbox_enabled: bool = Field(default=True, description="Enable Docker sandbox")
    sandbox_network_mode: Literal["none", "bridge", "host"] = Field(
        default="none", description="Docker network mode"
    )
    sandbox_cpu_quota: int = Field(
        default=200000, description="CPU quota (2 cores = 200000)"
    )
    sandbox_memory_limit: str = Field(default="4g", description="Memory limit")
    sandbox_pids_limit: int = Field(default=100, description="PID limit")
    sandbox_auto_remove: bool = Field(
        default=True, description="Auto-remove containers after execution"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    api_workers: int = Field(default=4, ge=1, description="Number of API workers")
    api_cors_origins: list[str] = Field(
        default=["*"], description="CORS allowed origins"
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    log_format: Literal["json", "console"] = Field(
        default="console", description="Log output format"
    )

    # Observability
    metrics_enabled: bool = Field(default=False, description="Enable Prometheus metrics")
    tracing_enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    jaeger_endpoint: str | None = Field(default=None, description="Jaeger collector endpoint")

    # Security
    security_enable_auth: bool = Field(default=False, description="Enable authentication")
    security_secret_key: str | None = Field(default=None, description="Secret key for JWT")
    security_token_expiry: int = Field(
        default=86400, description="JWT token expiry in seconds"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Returns:
        Singleton Settings instance
    """
    return Settings()
