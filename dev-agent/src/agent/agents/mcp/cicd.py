"""CI/CD Agent - Continuous Integration and Deployment Pipelines.

Specializes in:
- GitHub Actions workflows
- Pipeline configuration
- Build automation
- Deployment triggers
"""

from typing import Any

from agent.langgraph.state import SDLCPhase, SDLCState
from .base import AgentOutput, MCPAgentBase


class CICDAgent(MCPAgentBase):
    """
    CI/CD Agent for SDLC Phase 6.
    
    Responsibilities:
    - Create GitHub Actions workflows
    - Configure build pipelines
    - Set up deployment automation
    - Implement quality gates
    
    MCP Tools:
    - Filesystem: Write workflow files
    - GitHub: Manage workflows and secrets
    - Shell: Test pipeline commands
    """
    
    PHASE = SDLCPhase.CICD
    
    @property
    def role_description(self) -> str:
        return """DevOps Engineer and CI/CD Specialist.
        Expert in GitHub Actions, automated pipelines, and deployment automation."""
    
    @property
    def system_prompt(self) -> str:
        return """You are a Senior DevOps Engineer specializing in CI/CD.

## Core Responsibilities
- Create GitHub Actions workflows
- Configure automated pipelines
- Implement quality gates
- Set up deployment automation
- Manage secrets and environment variables

## GitHub Actions Best Practices

### Main CI Workflow
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run type-check

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run test -- --coverage
      - uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info

  build:
    runs-on: ubuntu-latest
    needs: [lint, type-check, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: build
          path: .next/
```

### Deployment Workflow
```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy-preview:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}

  deploy-production:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

### Database Migrations Workflow
```yaml
name: Database Migrations

on:
  push:
    branches: [main]
    paths:
      - 'prisma/migrations/**'
  workflow_dispatch:

jobs:
  migrate:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npx prisma migrate deploy
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Workflow Organization
```
.github/
├── workflows/
│   ├── ci.yml           # Main CI pipeline
│   ├── deploy.yml       # Deployment workflow
│   ├── migrations.yml   # Database migrations
│   ├── release.yml      # Release workflow
│   └── codeql.yml       # Security scanning
├── dependabot.yml       # Dependency updates
└── CODEOWNERS           # Code ownership
```

## Required Secrets
- VERCEL_TOKEN
- VERCEL_ORG_ID
- VERCEL_PROJECT_ID
- DATABASE_URL (production)
- CODECOV_TOKEN

## Quality Gates
- All tests must pass
- Type check must pass
- Lint must pass
- Code coverage >= 80%
- No high-severity vulnerabilities

## Output Format
1. Create workflow files
2. Set up quality gates
3. Configure deployment automation
4. Document required secrets

Write workflows to `/workspace/.github/workflows/`."""
    
    async def process(self, state: SDLCState) -> AgentOutput:
        """Process CI/CD phase from state."""
        test_output = state.get("phase_outputs", {}).get("testing", {})
        tests_passed = test_output.get("tests_passed", True)
        
        task_prompt = """## CI/CD Pipeline Setup

**Instructions:**
1. Create GitHub Actions CI workflow
   - Linting job
   - Type checking job
   - Testing job with coverage
   - Build job

2. Create deployment workflow
   - Preview deployments for PRs
   - Production deployment for main
   - Environment protection rules

3. Create database migration workflow
   - Run on schema changes
   - Safe deployment with rollback

4. Set up security scanning
   - CodeQL analysis
   - Dependency scanning

5. Create dependabot configuration
   - Weekly dependency updates
   - Auto-merge for patch versions

Write all files to `/workspace/.github/`

Document required secrets for repository settings."""
        
        messages = self._build_messages(state, task_prompt)
        response, tool_log = await self._execute_with_tools(messages)
        
        # Extract created workflows
        workflows_created = []
        for call in tool_log:
            if call["tool"] in ["write_file", "create_file"]:
                path = call.get("args", {}).get("path", "")
                if ".github" in path:
                    workflows_created.append(path)
        
        deliverables = {
            "raw_response": response,
            "tool_calls": tool_log,
            "workflows_created": workflows_created,
            "cicd_complete": True,
        }
        
        return AgentOutput(
            phase=self.PHASE,
            status="success",
            deliverables=deliverables,
            messages=[{"role": "assistant", "content": response}],
            artifacts=workflows_created,
            next_actions=[
                "Configure repository secrets",
                "Enable GitHub Actions",
                "Proceed to deployment",
            ],
            requires_approval=False,
        )
