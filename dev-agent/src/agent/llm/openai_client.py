"""OpenAI-compatible LLM client implementation."""

import asyncio
from typing import Any, AsyncIterator

import httpx
import tiktoken
from openai import AsyncOpenAI

from agent.config.settings import get_settings
from agent.llm.base import BaseLLMClient, LLMGenerationConfig, LLMMessage, LLMResponse


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible LLM client.

    Supports OpenAI API, Ollama, vLLM, and other OpenAI-compatible endpoints.
    """

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Initialize OpenAI client.

        Args:
            api_base: Base URL for API (defaults to settings)
            api_key: API key (defaults to settings)
            timeout: Request timeout in seconds (defaults to settings)
        """
        settings = get_settings()

        self.api_base = api_base or settings.llm_api_base_url
        self.api_key = api_key or settings.llm_api_key or "dummy-key"
        self.timeout = timeout or settings.llm_timeout

        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=httpx.Timeout(self.timeout),
        )

        # Initialize tokenizer (for OpenAI models)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback for non-OpenAI models
            self.encoding = None

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
        # Convert to OpenAI format
        openai_messages = [
            {
                "role": msg.role,
                "content": msg.content,
                **({"name": msg.name} if msg.name else {}),
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
            }
            for msg in messages
        ]

        # Build request parameters
        params: dict[str, Any] = {
            "model": config.model,
            "messages": openai_messages,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "frequency_penalty": config.frequency_penalty,
            "presence_penalty": config.presence_penalty,
        }

        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens

        if config.stop:
            params["stop"] = config.stop

        if config.tools:
            params["tools"] = config.tools

        if config.tool_choice:
            params["tool_choice"] = config.tool_choice

        # Make API request
        response = await self.client.chat.completions.create(**params)

        # Parse response
        choice = response.choices[0]
        message = choice.message

        return LLMResponse(
            content=message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens
                if response.usage
                else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason,
            tool_calls=[
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (message.tool_calls or [])
            ]
            if message.tool_calls
            else None,
        )

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
        # Convert to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Build request parameters
        params: dict[str, Any] = {
            "model": config.model,
            "messages": openai_messages,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "frequency_penalty": config.frequency_penalty,
            "presence_penalty": config.presence_penalty,
            "stream": True,
        }

        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens

        if config.stop:
            params["stop"] = config.stop

        # Make streaming API request
        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4

    async def close(self) -> None:
        """Close client and release resources."""
        await self.client.close()

    async def __aenter__(self) -> "OpenAIClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


async def create_llm_client() -> OpenAIClient:
    """Create LLM client from settings.

    Returns:
        Configured OpenAI client
    """
    return OpenAIClient()
