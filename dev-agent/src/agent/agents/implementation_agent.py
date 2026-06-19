"""Implementation Agent for code generation and development."""

from datetime import datetime, timezone
from typing import Any

from agent.agents.base import AgentRole, AgentTask, BaseAgent, TaskStatus


class ImplementationAgent(BaseAgent):
    """Specialized agent for code implementation and development."""

    @property
    def role_description(self) -> str:
        """Description of Implementation Agent role."""
        return (
            "Implementation Agent specializes in writing production-quality code, "
            "refactoring, debugging, and code optimization. Capabilities include "
            "code generation, bug fixing, performance optimization, and code review."
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for Implementation Agent."""
        return """You are an Implementation Agent specialized in software development.

**Your Expertise**:
- Writing clean, maintainable, well-documented code
- Following SOLID principles and design patterns
- Code refactoring and optimization
- Bug fixing and debugging
- Unit testing and TDD
- Code review and quality assurance
- Performance optimization
- Security best practices (input validation, SQL injection prevention, XSS prevention)

**Your Approach**:
1. **Understand Requirements**: Analyze what needs to be implemented
2. **Plan Implementation**: Break down into functions/classes/modules
3. **Write Code**: Implement following best practices and style guides
4. **Add Tests**: Write unit tests for new code
5. **Document**: Add docstrings, comments for complex logic
6. **Review**: Self-review for bugs, edge cases, security issues

**Code Quality Standards**:
- Clear, descriptive names for variables, functions, classes
- Single Responsibility Principle - one function, one purpose
- DRY (Don't Repeat Yourself) - extract common logic
- Error handling for edge cases and invalid inputs
- Input validation to prevent security vulnerabilities
- Comprehensive docstrings (Google/NumPy style)
- Type hints for function parameters and returns
- Unit tests with good coverage

**Security Checklist**:
- Validate and sanitize all user inputs
- Use parameterized queries to prevent SQL injection
- Escape output to prevent XSS
- Use secure random for tokens/secrets
- Never hard-code credentials
- Implement proper authentication and authorization
- Use HTTPS for sensitive data transmission

**Output Format**:
```python
# File: path/to/file.py

def function_name(param: Type) -> ReturnType:
    \"\"\"Brief description.

    Args:
        param: Parameter description

    Returns:
        Return value description

    Raises:
        ValueError: When invalid input
    \"\"\"
    # Implementation
    pass
```

**Best Practices**:
- Keep functions small and focused (< 50 lines)
- Limit function parameters (< 5)
- Avoid deep nesting (max 3-4 levels)
- Write self-documenting code with clear names
- Add comments only for non-obvious logic
- Handle errors gracefully with proper exceptions
"""

    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process code implementation task."""
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
            deliverables = self._extract_implementation(result)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = deliverables

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)

        return task

    def _extract_implementation(self, result: str) -> dict[str, Any]:
        """Extract implementation artifacts from output."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_role": "implementation",
            "raw_output": result,
            "deliverables": {
                "code_files": self._extract_code_files(result),
                "functions": self._extract_functions(result),
                "classes": self._extract_classes(result),
                "tests": self._extract_tests(result),
                "documentation": self._extract_documentation(result),
            },
            "metrics": {
                "lines_of_code": len([l for l in result.split("\n") if l.strip()]),
                "function_count": result.count("def "),
                "class_count": result.count("class "),
                "comment_lines": len([l for l in result.split("\n") if l.strip().startswith("#")]),
                "docstring_count": result.count('"""') // 2,
            },
            "quality_checks": {
                "has_docstrings": '"""' in result,
                "has_type_hints": "->" in result,
                "has_error_handling": "try:" in result or "except" in result,
                "has_input_validation": "if not" in result or "assert" in result,
            },
        }

    def _extract_code_files(self, text: str) -> list[dict[str, str]]:
        """Extract code file definitions."""
        files = []
        lines = text.split("\n")
        current_file = None
        file_content = []

        for line in lines:
            if line.strip().startswith("# File:") or line.strip().startswith("// File:"):
                if current_file:
                    files.append({"path": current_file, "content": "\n".join(file_content)})
                current_file = line.split("File:")[-1].strip()
                file_content = []
            elif current_file and line.strip():
                file_content.append(line)

        if current_file:
            files.append({"path": current_file, "content": "\n".join(file_content)})

        return files

    def _extract_functions(self, text: str) -> list[dict[str, str]]:
        """Extract function definitions."""
        functions = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if line.strip().startswith("def ") or line.strip().startswith("async def "):
                func_name = line.split("(")[0].split("def ")[-1].strip()
                # Get docstring if present
                docstring = ""
                if i + 1 < len(lines) and '"""' in lines[i + 1]:
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if '"""' in lines[j]:
                            docstring = lines[j].strip()
                            break

                functions.append({
                    "name": func_name,
                    "signature": line.strip(),
                    "docstring": docstring,
                    "line": i + 1,
                })

        return functions

    def _extract_classes(self, text: str) -> list[dict[str, str]]:
        """Extract class definitions."""
        classes = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if line.strip().startswith("class "):
                class_name = line.split("(")[0].split("class ")[-1].strip().rstrip(":")
                base_classes = ""
                if "(" in line:
                    base_classes = line.split("(")[1].split(")")[0]

                classes.append({
                    "name": class_name,
                    "bases": base_classes,
                    "line": i + 1,
                })

        return classes

    def _extract_tests(self, text: str) -> list[dict[str, str]]:
        """Extract test definitions."""
        tests = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if "def test_" in line or "async def test_" in line:
                test_name = line.split("(")[0].split("def ")[-1].strip()
                tests.append({
                    "name": test_name,
                    "line": i + 1,
                })

        return tests

    def _extract_documentation(self, text: str) -> dict[str, Any]:
        """Extract documentation elements."""
        return {
            "readme_sections": [l.strip() for l in text.split("\n") if l.strip().startswith("#")],
            "docstring_coverage": self._calculate_docstring_coverage(text),
            "comment_ratio": self._calculate_comment_ratio(text),
        }

    def _calculate_docstring_coverage(self, text: str) -> float:
        """Calculate percentage of functions with docstrings."""
        func_count = text.count("def ")
        docstring_count = text.count('"""')
        return (docstring_count / (func_count * 2)) if func_count > 0 else 0.0

    def _calculate_comment_ratio(self, text: str) -> float:
        """Calculate ratio of comment lines to code lines."""
        lines = text.split("\n")
        code_lines = len([l for l in lines if l.strip() and not l.strip().startswith("#")])
        comment_lines = len([l for l in lines if l.strip().startswith("#")])
        return comment_lines / code_lines if code_lines > 0 else 0.0


async def create_implementation_agent(
    llm_client: Any,
    tool_registry: Any,
    memory: Any | None = None,
) -> ImplementationAgent:
    """Factory function to create Implementation Agent."""
    from agent.agents.base import AgentConfig, AgentRole

    config = AgentConfig(
        role=AgentRole.IMPLEMENTATION,
        max_iterations=30,
        timeout_seconds=3600,  # 1 hour
        tools=["read_file", "write_file", "file_search", "shell_execute", "git_operations"],
    )

    return ImplementationAgent(
        config=config,
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory=memory,
    )
