"""Testing Agent for test generation and quality assurance."""

from datetime import datetime, timezone
from typing import Any

from agent.agents.base import AgentRole, AgentTask, BaseAgent, TaskStatus


class TestingAgent(BaseAgent):
    """Specialized agent for software testing and quality assurance."""

    @property
    def role_description(self) -> str:
        """Description of Testing Agent role."""
        return (
            "Testing Agent specializes in test strategy, test generation, and quality "
            "assurance. Capabilities include unit test creation, integration testing, "
            "E2E testing, coverage analysis, and test automation."
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for Testing Agent."""
        return """You are a Testing Agent specialized in software quality assurance.

**Your Expertise**:
- Test strategy and test planning
- Unit testing with pytest, unittest, Jest
- Integration testing and E2E testing
- Test coverage analysis and improvement
- Test-Driven Development (TDD)
- Mocking and test doubles
- Performance testing and load testing
- Security testing and vulnerability scanning

**Testing Principles**:
- F.I.R.S.T: Fast, Independent, Repeatable, Self-validating, Timely
- AAA Pattern: Arrange, Act, Assert
- Test edge cases and error conditions
- Aim for high coverage (>80%) with meaningful tests
- Test behavior, not implementation details
- Keep tests simple and focused

**Test Types**:
1. **Unit Tests**: Test individual functions/methods in isolation
2. **Integration Tests**: Test component interactions
3. **E2E Tests**: Test complete user workflows
4. **Performance Tests**: Test speed and resource usage
5. **Security Tests**: Test for vulnerabilities

**Output Format**:
```python
import pytest

def test_feature_name():
    \"\"\"Test description of what is being tested.\"\"\"
    # Arrange: Set up test data
    input_data = {"key": "value"}

    # Act: Execute the function under test
    result = function_under_test(input_data)

    # Assert: Verify expected behavior
    assert result == expected_value
    assert isinstance(result, ExpectedType)

def test_error_handling():
    \"\"\"Test that errors are handled correctly.\"\"\"
    with pytest.raises(ValueError):
        function_under_test(invalid_input)
```

**Coverage Goals**:
- Critical paths: 100% coverage
- Business logic: 90%+ coverage
- Utility functions: 80%+ coverage
- Overall project: 80%+ coverage

**Best Practices**:
- Write descriptive test names (test_function_when_condition_then_result)
- One assertion per test (or closely related assertions)
- Use fixtures for common setup
- Test both success and failure paths
- Include edge cases (null, empty, boundary values)
- Mock external dependencies (APIs, databases)
- Keep tests fast (<100ms per unit test)
"""

    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process testing task."""
        is_valid, error = await self.validate_task(task)
        if not is_valid:
            task.status = TaskStatus.FAILED
            task.error = error
            return task

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)

        try:
            prompt = self._build_prompt(task)
            result = await self.engine.execute(prompt)
            deliverables = self._extract_testing_artifacts(result)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = deliverables

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

        return task

    def _extract_testing_artifacts(self, result: str) -> dict[str, Any]:
        """Extract testing artifacts from output."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_role": "testing",
            "raw_output": result,
            "deliverables": {
                "test_files": self._extract_test_files(result),
                "test_cases": self._extract_test_cases(result),
                "fixtures": self._extract_fixtures(result),
                "coverage_strategy": self._extract_coverage_strategy(result),
            },
            "metrics": {
                "test_count": result.count("def test_"),
                "assertion_count": result.count("assert "),
                "fixture_count": result.count("@pytest.fixture"),
                "mock_count": result.count("mock") + result.count("Mock"),
            },
            "quality_indicators": {
                "has_docstrings": '"""' in result or "'''" in result,
                "uses_fixtures": "@pytest.fixture" in result or "@fixture" in result,
                "tests_errors": "pytest.raises" in result or "with raises" in result,
                "uses_mocks": "mock" in result.lower(),
                "follows_aaa": "# Arrange" in result or "# Act" in result or "# Assert" in result,
            },
        }

    def _extract_test_files(self, text: str) -> list[dict[str, str]]:
        """Extract test file definitions."""
        files = []
        lines = text.split("\n")
        current_file = None
        file_content = []

        for line in lines:
            if "test_" in line and (".py" in line or ".js" in line or ".ts" in line):
                if "File:" in line or "#" in line[:5]:
                    if current_file:
                        files.append({"path": current_file, "content": "\n".join(file_content)})
                    current_file = line.split(":")[-1].strip() if ":" in line else line.strip("#").strip()
                    file_content = []
            elif current_file:
                file_content.append(line)

        if current_file:
            files.append({"path": current_file, "content": "\n".join(file_content)})

        return files

    def _extract_test_cases(self, text: str) -> list[dict[str, Any]]:
        """Extract test case definitions."""
        test_cases = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if "def test_" in line or "it(" in line or "test(" in line:
                test_name = ""
                if "def test_" in line:
                    test_name = line.split("(")[0].split("def ")[-1].strip()
                elif "it(" in line:
                    test_name = line.split("it(")[1].split(",")[0].strip('"').strip("'")

                # Get docstring or description
                description = ""
                if i + 1 < len(lines) and ('"""' in lines[i + 1] or "'''" in lines[i + 1]):
                    description = lines[i + 1].strip().strip('"""').strip("'''")

                # Count assertions in this test
                assertion_count = 0
                for j in range(i, min(i + 20, len(lines))):
                    if "assert" in lines[j] or "expect(" in lines[j]:
                        assertion_count += 1
                    if j > i and ("def " in lines[j] or "class " in lines[j]):
                        break

                test_cases.append({
                    "name": test_name,
                    "description": description,
                    "assertions": assertion_count,
                    "line": i + 1,
                })

        return test_cases

    def _extract_fixtures(self, text: str) -> list[dict[str, str]]:
        """Extract test fixtures."""
        fixtures = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if "@pytest.fixture" in line or "@fixture" in line:
                # Next line should be the fixture function
                if i + 1 < len(lines):
                    func_line = lines[i + 1]
                    if "def " in func_line:
                        fixture_name = func_line.split("(")[0].split("def ")[-1].strip()
                        fixtures.append({
                            "name": fixture_name,
                            "decorator": line.strip(),
                            "line": i + 1,
                        })

        return fixtures

    def _extract_coverage_strategy(self, text: str) -> dict[str, Any]:
        """Extract coverage strategy from output."""
        strategy = {
            "target_coverage": 80.0,
            "critical_paths": [],
            "untested_areas": [],
            "recommendations": [],
        }

        lines = text.split("\n")
        for line in lines:
            if "coverage" in line.lower():
                if "%" in line:
                    try:
                        # Extract percentage
                        pct = float(line.split("%")[0].split()[-1])
                        strategy["target_coverage"] = pct
                    except (ValueError, IndexError):
                        pass

            if "critical" in line.lower() and ("path" in line.lower() or "test" in line.lower()):
                strategy["critical_paths"].append(line.strip())

            if any(keyword in line.lower() for keyword in ["untested", "not covered", "missing coverage"]):
                strategy["untested_areas"].append(line.strip())

            if any(keyword in line.lower() for keyword in ["recommend", "should test", "need to test"]):
                strategy["recommendations"].append(line.strip())

        return strategy


async def create_testing_agent(
    llm_client: Any,
    tool_registry: Any,
    memory: Any | None = None,
) -> TestingAgent:
    """Factory function to create Testing Agent."""
    from agent.agents.base import AgentConfig, AgentRole

    config = AgentConfig(
        role=AgentRole.TESTING,
        max_iterations=25,
        timeout_seconds=2400,  # 40 minutes
        tools=["read_file", "write_file", "file_search", "shell_execute"],
    )

    return TestingAgent(
        config=config,
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory=memory,
    )
