"""Testing Agent - Test Generation and Quality Assurance.

Specializes in:
- Unit test generation
- Integration test creation
- E2E test planning
- Test coverage analysis
"""

from typing import Any

from agent.langgraph.state import SDLCPhase, SDLCState, TestReport
from .base import AgentOutput, MCPAgentBase


class TestingAgent(MCPAgentBase):
    """
    Testing Agent for SDLC Phase 5.
    
    Responsibilities:
    - Generate unit tests for components/functions
    - Create integration tests
    - Write E2E test scenarios
    - Analyze test coverage
    - Identify edge cases
    
    MCP Tools:
    - Filesystem: Read code, write tests
    - Shell: Run test commands
    - Git: Track test files
    """
    
    PHASE = SDLCPhase.TESTING
    
    @property
    def role_description(self) -> str:
        return """QA Engineer and Test Automation Specialist.
        Expert in testing strategies, test-driven development, and quality assurance."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior QA Engineer specializing in test automation.

## Core Responsibilities
- Generate comprehensive test suites
- Ensure proper test coverage
- Write maintainable test code
- Identify edge cases and error scenarios
- Create both unit and integration tests

## Testing Stack
- Unit Tests: Vitest (modern, fast, Vite-compatible)
- Component Tests: React Testing Library
- E2E Tests: Playwright
- Mocking: MSW (Mock Service Worker)
- Coverage: Istanbul/c8

## Test Conventions

### Unit Tests (Vitest)
```typescript
import { describe, it, expect, vi } from 'vitest';
import { myFunction } from './my-function';

describe('myFunction', () => {
  it('should return expected value', () => {
    expect(myFunction('input')).toBe('expected');
  });

  it('should handle edge cases', () => {
    expect(myFunction('')).toBeNull();
    expect(() => myFunction(null)).toThrow();
  });
});
```

### Component Tests (React Testing Library)
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent title="Test" />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('handles user interaction', async () => {
    render(<MyComponent onSubmit={vi.fn()} />);
    await fireEvent.click(screen.getByRole('button'));
    expect(onSubmit).toHaveBeenCalled();
  });
});
```

### API Mocking (MSW)
```typescript
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json([{ id: 1, name: 'John' }]);
  }),
];

const server = setupServer(...handlers);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### E2E Tests (Playwright)
```typescript
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('user can log in', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'password');
    await page.click('[type="submit"]');
    await expect(page).toHaveURL('/dashboard');
  });
});
```

## Test Organization
```
tests/
├── unit/              # Unit tests
│   ├── lib/           # Utility tests
│   └── components/    # Component unit tests
├── integration/       # Integration tests
│   ├── api/           # API tests
│   └── features/      # Feature tests
└── e2e/              # End-to-end tests
    ├── auth.spec.ts
    └── dashboard.spec.ts
```

## Coverage Requirements
- Statement coverage: 80%+
- Branch coverage: 70%+
- Function coverage: 80%+
- Focus on critical paths

## Test Quality Standards
- Descriptive test names (should/when/then)
- One assertion per test when possible
- No test interdependencies
- Clean setup and teardown
- Mock external dependencies

## Output Format
1. Generate test files for each source file
2. Run tests and report results
3. Generate coverage report
4. Document any uncovered edge cases

Write tests to `/workspace/tests/` directory."""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process testing phase from state."""
        code_output = state.get("phase_outputs", {}).get("coding", {})
        files_created = code_output.get("files_created", [])
        
        task_prompt = f"""## Test Generation Task

**Files to Test:**
{chr(10).join(files_created) if files_created else "All source files in /workspace/src/"}

**Instructions:**
1. Analyze the source code
2. Generate unit tests for functions and utilities
3. Create component tests for React components
4. Write integration tests for API routes
5. Run the tests and report results
6. Generate coverage report

Focus on:
- Testing happy paths and error cases
- Edge cases and boundary conditions
- User interactions for components
- API response handling

Write tests to:
- `/workspace/tests/unit/` for unit tests
- `/workspace/tests/integration/` for integration tests

After writing tests, run:
```bash
npm run test -- --coverage
```"""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        # Check for test results in tool log
        test_passed = True
        coverage = None
        for call in tool_log:
            if call["tool"] == "run_command":
                result = call.get("result", "")
                if "FAIL" in result.upper():
                    test_passed = False
                if "coverage" in result.lower():
                    coverage = result
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "tests_passed": test_passed,
            "coverage": coverage,
            "testing_complete": True,
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success" if test_passed else "failed",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=["tests/"],
            next_actions=[
                "Review test results" if not test_passed else "Proceed to CI/CD setup",
                "Fix failing tests" if not test_passed else "Review coverage report",
            ],
            requires_approval=False,
            error="Some tests failed" if not test_passed else None,
        )
