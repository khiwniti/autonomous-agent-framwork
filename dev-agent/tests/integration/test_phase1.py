"""Integration tests for Phase 1 components."""

import pytest

from agent.config.settings import get_settings
from agent.core.engine import ReActEngine
from agent.llm.base import LLMGenerationConfig, LLMMessage
from agent.llm.openai_client import OpenAIClient
from agent.memory.working import WorkingMemory
from agent.tools.base import get_tool_registry
from agent.tools.calculator import CalculatorTool, register_calculator_tool


@pytest.fixture
def tool_registry():
    """Create tool registry with calculator tool."""
    registry = get_tool_registry()
    registry.clear()  # Clear any existing tools
    register_calculator_tool()
    return registry


@pytest.mark.asyncio
class TestLLMIntegration:
    """Test LLM client integration."""

    async def test_openai_client_initialization(self):
        """Test OpenAI client can be initialized."""
        client = OpenAIClient()
        assert client is not None
        await client.close()

    async def test_token_counting(self):
        """Test token counting functionality."""
        client = OpenAIClient()
        text = "Hello, world!"
        count = await client.count_tokens(text)
        assert count > 0
        await client.close()


@pytest.mark.asyncio
class TestToolFramework:
    """Test tool framework."""

    async def test_calculator_tool_basic(self):
        """Test calculator tool basic operation."""
        tool = CalculatorTool()

        result = await tool.execute(expression="2 + 3")
        assert result.success is True
        assert result.output == 5.0

    async def test_calculator_tool_complex(self):
        """Test calculator with complex expression."""
        tool = CalculatorTool()

        result = await tool.execute(expression="2 * (3 + 4) ** 2")
        assert result.success is True
        assert result.output == 98.0

    async def test_calculator_tool_error(self):
        """Test calculator error handling."""
        tool = CalculatorTool()

        result = await tool.execute(expression="2 +")
        assert result.success is False
        assert result.error is not None

    async def test_tool_registry(self, tool_registry):
        """Test tool registry operations."""
        assert len(tool_registry.list_tools()) == 1
        assert "calculator" in tool_registry.list_tools()

        tool = tool_registry.get("calculator")
        assert tool is not None
        assert tool.name == "calculator"

    async def test_openai_tool_format(self):
        """Test OpenAI tool format conversion."""
        tool = CalculatorTool()
        openai_format = tool.to_openai_tool()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "calculator"
        assert "description" in openai_format["function"]
        assert "parameters" in openai_format["function"]


@pytest.mark.asyncio
class TestMemorySystem:
    """Test working memory system."""

    async def test_memory_set_get(self):
        """Test basic memory operations."""
        async with WorkingMemory() as memory:
            await memory.set("test_key", "test_value")
            value = await memory.get("test_key")
            assert value == "test_value"

    async def test_memory_expiration(self):
        """Test memory TTL expiration."""
        async with WorkingMemory(default_ttl=1) as memory:
            await memory.set("expire_key", "expire_value", ttl=0)
            # Entry should already be expired
            value = await memory.get("expire_key")
            assert value is None

    async def test_memory_delete(self):
        """Test memory deletion."""
        async with WorkingMemory() as memory:
            await memory.set("delete_key", "delete_value")
            assert await memory.exists("delete_key") is True

            await memory.delete("delete_key")
            assert await memory.exists("delete_key") is False

    async def test_memory_keys(self):
        """Test listing keys with pattern."""
        async with WorkingMemory() as memory:
            await memory.set("user:1", "value1")
            await memory.set("user:2", "value2")
            await memory.set("session:1", "value3")

            user_keys = await memory.keys("user:*")
            assert len(user_keys) == 2
            assert "user:1" in user_keys
            assert "user:2" in user_keys

    async def test_memory_stats(self):
        """Test memory statistics."""
        async with WorkingMemory() as memory:
            await memory.set("stat_key1", "value1")
            await memory.set("stat_key2", "value2")

            stats = await memory.get_stats()
            assert stats["backend"] == "in-memory"
            assert stats["keys"] >= 2


@pytest.mark.asyncio
class TestReActEngine:
    """Test ReAct reasoning engine."""

    async def test_engine_initialization(self, tool_registry):
        """Test engine can be initialized."""
        async with OpenAIClient() as client:
            engine = ReActEngine(
                llm_client=client,
                tool_registry=tool_registry,
                max_iterations=5,
            )
            assert engine is not None
            assert engine.max_iterations == 5

    async def test_loop_detection(self, tool_registry):
        """Test infinite loop detection."""
        async with OpenAIClient() as client:
            engine = ReActEngine(
                llm_client=client,
                tool_registry=tool_registry,
                max_iterations=10,
            )

            # Simulate repeated actions
            engine.action_history = ["action1"] * 6
            assert engine._detect_loop() is True

    async def test_progress_summary(self, tool_registry):
        """Test progress summary generation."""
        async with OpenAIClient() as client:
            engine = ReActEngine(
                llm_client=client,
                tool_registry=tool_registry,
            )

            summary = engine._build_progress_summary()
            assert "No steps taken yet" in summary

    async def test_react_response_parsing(self, tool_registry):
        """Test ReAct response format parsing."""
        async with OpenAIClient() as client:
            engine = ReActEngine(
                llm_client=client,
                tool_registry=tool_registry,
            )

            response = """
Thought: I need to calculate 2 + 3
Action: calculator
Action Input: {"expression": "2 + 3"}
"""

            thought, action, action_input = engine._parse_react_response(response)

            assert "calculate" in thought.lower()
            assert action == "calculator"
            assert "expression" in action_input


@pytest.mark.asyncio
class TestConfigSystem:
    """Test configuration system."""

    def test_settings_load(self):
        """Test settings can be loaded."""
        settings = get_settings()
        assert settings is not None
        assert settings.app_name == "Autonomous Dev Agent"

    def test_settings_defaults(self):
        """Test default configuration values."""
        settings = get_settings()
        assert settings.llm_provider in ["openai", "ollama", "vllm"]
        assert settings.agent_max_iterations > 0
        assert settings.agent_reflection_interval > 0

    def test_settings_validation(self):
        """Test configuration validation."""
        settings = get_settings()
        # Temperature should be between 0 and 2
        assert 0.0 <= settings.llm_temperature <= 2.0
        # Max iterations should be positive
        assert settings.agent_max_iterations > 0


@pytest.mark.asyncio
class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.skip(reason="Requires LLM API key")
    async def test_simple_calculation_task(self, tool_registry):
        """Test simple calculation task end-to-end.

        NOTE: This test requires a valid LLM API key and will be skipped by default.
        """
        async with OpenAIClient() as client:
            async with WorkingMemory() as memory:
                engine = ReActEngine(
                    llm_client=client,
                    tool_registry=tool_registry,
                    max_iterations=10,
                )

                result = await engine.execute(
                    "Calculate 15 * 23 + 47 and tell me the result"
                )

                # Check basic results
                assert result is not None
                assert result.iterations > 0

                # If successful, output should contain the answer
                if result.success:
                    # 15 * 23 + 47 = 345 + 47 = 392
                    assert "392" in str(result.output) or any(
                        "392" in str(step.observation)
                        for step in result.steps
                    )

                await engine.close()
