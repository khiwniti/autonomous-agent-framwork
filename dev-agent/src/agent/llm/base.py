"""Base LLM client interface and data models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """Message in a conversation."""

    role: Literal["system", "user", "assistant", "tool"] = Field(
        description="Message role"
    )
    content: str = Field(description="Message content")
    name: str | None = Field(default=None, description="Optional name (for tool messages)")
    tool_call_id: str | None = Field(
        default=None, description="Tool call ID (for tool response messages)"
    )

    class Config:
        """Pydantic configuration."""

        frozen = True


class LLMResponse(BaseModel):
    """Response from LLM."""

    content: str = Field(description="Response content")
    model: str = Field(description="Model used")
    usage: dict[str, Any] = Field(description="Token usage information")
    finish_reason: str | None = Field(default=None, description="Reason for completion")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None, description="Tool calls made by LLM"
    )


@dataclass
class LLMGenerationConfig:
    """Configuration for LLM generation."""

    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    stream: bool = False


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        config: LLMGenerationConfig,
    ) -> LLMResponse:
        """Generate completion from messages.

        Args:
            messages: List of conversation messages
            config: Generation configuration

        Returns:
            LLM response with content and metadata
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        config: LLMGenerationConfig,
    ) -> AsyncIterator[str]:
        """Generate streaming completion from messages.

        Args:
            messages: List of conversation messages
            config: Generation configuration

        Yields:
            Streamed token chunks
        """
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close client and release resources."""
        pass
