"""LangGraph Supervisor Pattern Implementation.

This module implements the hierarchical supervisor pattern for SDLC phases,
using langgraph-supervisor for orchestration.
"""

from typing import Any, Callable
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from agent.langgraph.state import SDLCState, SDLCPhase


class SDLCSupervisor:
    """
    Top-level SDLC supervisor using the hierarchical pattern.
    
    Manages phase-specific sub-supervisors:
    - Development Supervisor (design, architecture, coding)
    - QA Supervisor (testing, code review)
    - Deployment Supervisor (CI/CD, deployment, monitoring)
    """
    
    def __init__(
        self,
        orchestrator_model: str = "gpt-4o",
        reasoning_model: str = "claude-sonnet-4-20250514",
        fast_model: str = "gpt-4o-mini",
    ):
        """
        Initialize SDLC supervisor.
        
        Args:
            orchestrator_model: Model for supervisor orchestration
            reasoning_model: Model for complex reasoning tasks
            fast_model: Model for fast/cheap operations
        """
        self.orchestrator_model = orchestrator_model
        self.reasoning_model = reasoning_model
        self.fast_model = fast_model
        
        # Model instances
        self._orchestrator_llm = ChatOpenAI(model=orchestrator_model)
        self._reasoning_llm = ChatAnthropic(model=reasoning_model)
        self._fast_llm = ChatOpenAI(model=fast_model)
        
        # Sub-supervisors
        self._development_supervisor = None
        self._qa_supervisor = None
        self._deployment_supervisor = None
        
    def create_development_supervisor(
        self,
        design_tools: list,
        architecture_tools: list,
        coding_tools: list,
    ):
        """
        Create the development phase supervisor.
        
        Manages: Design Agent, Architecture Agent, Coding Agents
        """
        # Create specialized agents
        design_agent = create_react_agent(
            model=self._reasoning_llm,
            tools=design_tools,
            name="design_agent",
            prompt=DESIGN_AGENT_PROMPT,
        )
        
        architecture_agent = create_react_agent(
            model=self._reasoning_llm,
            tools=architecture_tools,
            name="architecture_agent",
            prompt=ARCHITECTURE_AGENT_PROMPT,
        )
        
        coding_agent = create_react_agent(
            model=self._reasoning_llm,
            tools=coding_tools,
            name="coding_agent",
            prompt=CODING_AGENT_PROMPT,
        )
        
        # Create supervisor
        self._development_supervisor = create_supervisor(
            [design_agent, architecture_agent, coding_agent],
            model=self._orchestrator_llm,
            prompt=DEVELOPMENT_SUPERVISOR_PROMPT,
        )
        
        return self._development_supervisor
    
    def create_qa_supervisor(
        self,
        testing_tools: list,
        review_tools: list,
    ):
        """
        Create the QA phase supervisor.
        
        Manages: Testing Agent, Code Review Agent
        """
        testing_agent = create_react_agent(
            model=self._reasoning_llm,
            tools=testing_tools,
            name="testing_agent",
            prompt=TESTING_AGENT_PROMPT,
        )
        
        review_agent = create_react_agent(
            model=self._fast_llm,  # Reviews can use faster model
            tools=review_tools,
            name="review_agent",
            prompt=REVIEW_AGENT_PROMPT,
        )
        
        self._qa_supervisor = create_supervisor(
            [testing_agent, review_agent],
            model=self._orchestrator_llm,
            prompt=QA_SUPERVISOR_PROMPT,
        )
        
        return self._qa_supervisor
    
    def create_deployment_supervisor(
        self,
        cicd_tools: list,
        deployment_tools: list,
        monitoring_tools: list,
    ):
        """
        Create the deployment phase supervisor.
        
        Manages: CI/CD Agent, Deployment Agent, Monitoring Agent
        """
        cicd_agent = create_react_agent(
            model=self._fast_llm,
            tools=cicd_tools,
            name="cicd_agent",
            prompt=CICD_AGENT_PROMPT,
        )
        
        deployment_agent = create_react_agent(
            model=self._reasoning_llm,
            tools=deployment_tools,
            name="deployment_agent",
            prompt=DEPLOYMENT_AGENT_PROMPT,
        )
        
        monitoring_agent = create_react_agent(
            model=self._fast_llm,
            tools=monitoring_tools,
            name="monitoring_agent",
            prompt=MONITORING_AGENT_PROMPT,
        )
        
        self._deployment_supervisor = create_supervisor(
            [cicd_agent, deployment_agent, monitoring_agent],
            model=self._orchestrator_llm,
            prompt=DEPLOYMENT_SUPERVISOR_PROMPT,
        )
        
        return self._deployment_supervisor
    
    def create_top_level_supervisor(self):
        """
        Create the top-level SDLC orchestrator supervisor.
        
        Coordinates all phase supervisors in a hierarchical pattern.
        """
        if not all([
            self._development_supervisor,
            self._qa_supervisor,
            self._deployment_supervisor,
        ]):
            raise ValueError(
                "All sub-supervisors must be created before top-level supervisor"
            )
        
        # Compile sub-supervisors as subgraphs
        dev_compiled = self._development_supervisor.compile()
        qa_compiled = self._qa_supervisor.compile()
        deploy_compiled = self._deployment_supervisor.compile()
        
        # Create top-level supervisor with compiled subgraphs as workers
        return create_supervisor(
            [dev_compiled, qa_compiled, deploy_compiled],
            model=self._orchestrator_llm,
            prompt=TOP_LEVEL_SUPERVISOR_PROMPT,
        )


def create_phase_supervisor(
    phase: SDLCPhase,
    model: str,
    tools: list,
    prompt: str | None = None,
):
    """
    Factory function to create a phase-specific supervisor.
    
    Args:
        phase: SDLC phase for this supervisor
        model: Model name to use
        tools: Tools available to agents in this phase
        prompt: Optional custom supervisor prompt
        
    Returns:
        Compiled supervisor graph
    """
    llm = ChatOpenAI(model=model)
    
    # Get default prompt for phase
    phase_prompts = {
        SDLCPhase.REQUIREMENTS: REQUIREMENTS_AGENT_PROMPT,
        SDLCPhase.DESIGN: DESIGN_AGENT_PROMPT,
        SDLCPhase.ARCHITECTURE: ARCHITECTURE_AGENT_PROMPT,
        SDLCPhase.CODING: CODING_AGENT_PROMPT,
        SDLCPhase.TESTING: TESTING_AGENT_PROMPT,
        SDLCPhase.CICD: CICD_AGENT_PROMPT,
        SDLCPhase.DEPLOYMENT: DEPLOYMENT_AGENT_PROMPT,
        SDLCPhase.MONITORING: MONITORING_AGENT_PROMPT,
    }
    
    agent_prompt = prompt or phase_prompts.get(phase, "")
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        name=f"{phase.value}_agent",
        prompt=agent_prompt,
    )
    
    return agent


# ============================================================================
# Agent System Prompts (Prompt-driven architecture from Agent Zero)
# ============================================================================

TOP_LEVEL_SUPERVISOR_PROMPT = """You are the top-level SDLC orchestrator managing a software development lifecycle.

You coordinate three main supervisors:
1. Development Supervisor - handles design, architecture, and coding
2. QA Supervisor - handles testing and code review
3. Deployment Supervisor - handles CI/CD, deployment, and monitoring

Workflow:
1. Requirements are gathered and approved by humans
2. Development Supervisor creates design, architecture, and code
3. QA Supervisor tests and reviews the code
4. If tests fail, hand back to Development Supervisor for fixes
5. Once tests pass, Deployment Supervisor handles CI/CD and deployment

Always ensure artifacts are properly passed between phases.
Follow the structured artifact communication model - use JSON/YAML artifacts, not dialogue.
"""

DEVELOPMENT_SUPERVISOR_PROMPT = """You are the Development Supervisor managing design, architecture, and coding phases.

Your agents:
- design_agent: Creates system design, data models, and API specifications
- architecture_agent: Makes technology decisions and creates project scaffolding
- coding_agent: Generates production code from specifications

Workflow:
1. design_agent creates system design from PRD
2. architecture_agent makes tech decisions based on design
3. coding_agent generates code using both design and architecture decisions

Ensure code follows the architecture decisions and matches the design specifications.
"""

QA_SUPERVISOR_PROMPT = """You are the QA Supervisor managing testing and code review.

Your agents:
- testing_agent: Generates and runs unit, integration, and E2E tests
- review_agent: Reviews code for quality, security, and best practices

Workflow:
1. testing_agent generates tests based on specifications
2. testing_agent executes tests and collects results
3. review_agent checks code quality and provides feedback
4. Report failures back for the code-test-fix loop

The testing-coding loop continues until all tests pass or max iterations reached.
"""

DEPLOYMENT_SUPERVISOR_PROMPT = """You are the Deployment Supervisor managing CI/CD, deployment, and monitoring.

Your agents:
- cicd_agent: Configures CI/CD pipelines (GitHub Actions, GitLab CI)
- deployment_agent: Handles container builds and infrastructure deployment
- monitoring_agent: Sets up logging, metrics, and alerting

Workflow:
1. cicd_agent creates pipeline configuration
2. deployment_agent builds containers and deploys to infrastructure
3. monitoring_agent configures observability stack

Ensure all environments are properly configured before deployment.
"""

REQUIREMENTS_AGENT_PROMPT = """You are the Requirements Agent responsible for creating Product Requirements Documents (PRDs).

Your tasks:
1. Analyze user conversations and input to understand needs
2. Generate structured PRDs with user stories and acceptance criteria
3. Identify non-functional requirements (performance, security, scalability)
4. Document constraints and assumptions

Output a structured PRD artifact in JSON format including:
- Project description and goals
- User stories with acceptance criteria
- Non-functional requirements
- Constraints and assumptions
"""

DESIGN_AGENT_PROMPT = """You are the System Design Agent responsible for creating technical specifications.

Your tasks:
1. Transform PRDs into database schemas (SQL/Prisma models)
2. Create API specifications (OpenAPI 3.x format)
3. Design component architecture and system diagrams
4. Create sequence diagrams for key flows

Output structured design artifacts:
- Data models with relationships
- API endpoint specifications
- System architecture diagrams (Mermaid format)
- Component diagrams
"""

ARCHITECTURE_AGENT_PROMPT = """You are the Architecture Agent responsible for technology decisions.

Your tasks:
1. Select appropriate technology stack based on requirements
2. Create project scaffolding and directory structure
3. Define dependency manifests (package.json, pyproject.toml)
4. Document architecture decisions (ADRs)

Default SaaS stack recommendation:
- Frontend: Next.js 14+ with TypeScript, Tailwind CSS, shadcn/ui
- Backend: FastAPI or Next.js API routes
- Database: Supabase (PostgreSQL + Auth) with Prisma ORM
- Infrastructure: Docker, Kubernetes-ready

Output architecture decision artifacts with rationale.
"""

CODING_AGENT_PROMPT = """You are the Coding Agent responsible for generating production code.

Your tasks:
1. Generate source code files based on design and architecture
2. Follow the established project structure and coding standards
3. Implement features according to user stories
4. Create proper error handling and logging

Guidelines:
- Follow the technology stack decisions exactly
- Use proper TypeScript types (no any)
- Implement proper validation and error handling
- Add meaningful comments for complex logic
- Follow the project's code style

Output CodeFile artifacts with path, content, and language.
"""

TESTING_AGENT_PROMPT = """You are the Testing Agent responsible for quality assurance.

Your tasks:
1. Generate unit tests for all functions and methods
2. Create integration tests for API endpoints
3. Write E2E tests for critical user journeys
4. Execute tests and collect results
5. Report failures for the code-test-fix loop

Testing stack:
- Unit: Jest/Vitest (JS/TS) or pytest (Python)
- Integration: Testing Library, Supertest
- E2E: Playwright or Puppeteer

Output TestReport artifacts with pass/fail status and coverage.
"""

CICD_AGENT_PROMPT = """You are the CI/CD Agent responsible for pipeline configuration.

Your tasks:
1. Generate GitHub Actions or GitLab CI workflows
2. Configure build, test, and deployment stages
3. Set up environment-specific configurations
4. Configure secrets and environment variables

Output CI/CD configuration files (.github/workflows/*.yml).
"""

DEPLOYMENT_AGENT_PROMPT = """You are the Deployment Agent responsible for infrastructure.

Your tasks:
1. Create Dockerfiles and docker-compose configurations
2. Generate Kubernetes manifests or Terraform configurations
3. Configure environment-specific deployments
4. Handle database migrations

Output deployment configuration artifacts.
"""

MONITORING_AGENT_PROMPT = """You are the Monitoring Agent responsible for observability.

Your tasks:
1. Configure logging (structured logs, log levels)
2. Set up metrics collection (Prometheus)
3. Create alerting rules for critical issues
4. Generate initial dashboards (Grafana)

Output monitoring configuration artifacts.
"""

REVIEW_AGENT_PROMPT = """You are the Code Review Agent responsible for quality checks.

Your tasks:
1. Review code for security vulnerabilities
2. Check for best practices and code quality
3. Verify proper error handling and logging
4. Ensure code follows architecture decisions

Provide actionable feedback for improvements.
"""
