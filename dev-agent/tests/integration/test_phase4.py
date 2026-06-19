"""Integration tests for Phase 4: SDLC Specialized Agents."""

import pytest
from datetime import datetime, timezone

from agent.agents import (
    AgentRole,
    AgentTask,
    TaskStatus,
    create_requirements_agent,
    create_architecture_agent,
    create_implementation_agent,
    create_testing_agent,
    create_deployment_agent,
    create_operations_agent,
)
from agent.core.orchestrator import (
    AgentOrchestrator,
    Workflow,
    WorkflowStage,
    WorkflowStatus,
    create_orchestrator,
)
from agent.llm.mock import MockLLMClient
from agent.memory.working import WorkingMemory
from agent.tools.base import ToolRegistry


@pytest.fixture
def llm_client():
    """Create mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def tool_registry():
    """Create tool registry."""
    return ToolRegistry()


@pytest.fixture
def memory():
    """Create working memory."""
    return WorkingMemory()


class TestRequirementsAgent:
    """Test Requirements Agent functionality."""

    @pytest.mark.asyncio
    async def test_create_requirements_agent(self, llm_client, tool_registry, memory):
        """Test creating requirements agent."""
        agent = await create_requirements_agent(llm_client, tool_registry, memory)
        assert agent is not None
        assert agent.config.role == AgentRole.REQUIREMENTS
        assert "user story" in agent.role_description.lower()

    @pytest.mark.asyncio
    async def test_process_requirements_task(self, llm_client, tool_registry, memory):
        """Test processing requirements gathering task."""
        agent = await create_requirements_agent(llm_client, tool_registry, memory)

        task = AgentTask(
            id="req_001",
            role=AgentRole.REQUIREMENTS,
            objective="Gather requirements for user authentication system",
            context={"project": "auth_system"},
        )

        # Mock LLM response with user stories
        llm_client.set_mock_response(
            """As a user, I want to log in with email and password so that I can access my account.

Acceptance Criteria:
- Given a valid email and password, when I submit the login form, then I should be logged in
- Given invalid credentials, when I submit the login form, then I should see an error message

Priority: Must have
"""
        )

        result = await agent.process_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert "deliverables" in result.result
        assert "user_stories" in result.result["deliverables"]

    @pytest.mark.asyncio
    async def test_extract_user_stories(self, llm_client, tool_registry, memory):
        """Test user story extraction."""
        agent = await create_requirements_agent(llm_client, tool_registry, memory)

        text = """
As a user, I want to reset my password so that I can regain access to my account.
As an admin, I want to manage user permissions so that I can control access.
"""

        stories = agent._extract_user_stories(text)
        assert len(stories) >= 2
        assert any("reset my password" in story["story"].lower() for story in stories)


class TestArchitectureAgent:
    """Test Architecture Agent functionality."""

    @pytest.mark.asyncio
    async def test_create_architecture_agent(self, llm_client, tool_registry, memory):
        """Test creating architecture agent."""
        agent = await create_architecture_agent(llm_client, tool_registry, memory)
        assert agent is not None
        assert agent.config.role == AgentRole.ARCHITECTURE
        assert "architecture" in agent.role_description.lower()

    @pytest.mark.asyncio
    async def test_process_architecture_task(self, llm_client, tool_registry, memory):
        """Test processing architecture design task."""
        agent = await create_architecture_agent(llm_client, tool_registry, memory)

        task = AgentTask(
            id="arch_001",
            role=AgentRole.ARCHITECTURE,
            objective="Design architecture for e-commerce platform",
            context={"requirements": "User authentication, product catalog, shopping cart"},
        )

        llm_client.set_mock_response(
            """## System Architecture

### Components:
- API Gateway
- Authentication Service
- Product Service
- Cart Service

### Tech Stack:
- Backend: Python/FastAPI
- Database: PostgreSQL
- Cache: Redis
"""
        )

        result = await agent.process_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert "deliverables" in result.result


class TestImplementationAgent:
    """Test Implementation Agent functionality."""

    @pytest.mark.asyncio
    async def test_create_implementation_agent(self, llm_client, tool_registry, memory):
        """Test creating implementation agent."""
        agent = await create_implementation_agent(llm_client, tool_registry, memory)
        assert agent is not None
        assert agent.config.role == AgentRole.IMPLEMENTATION
        assert "implementation" in agent.role_description.lower()

    @pytest.mark.asyncio
    async def test_process_implementation_task(self, llm_client, tool_registry, memory):
        """Test processing code implementation task."""
        agent = await create_implementation_agent(llm_client, tool_registry, memory)

        task = AgentTask(
            id="impl_001",
            role=AgentRole.IMPLEMENTATION,
            objective="Implement user authentication endpoint",
            context={"architecture": "FastAPI with JWT"},
        )

        llm_client.set_mock_response(
            """```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/login")
async def login(request: LoginRequest) -> dict:
    '''Authenticate user and return JWT token.'''
    # Validate credentials
    if not validate_user(request.email, request.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate JWT token
    token = generate_jwt_token(request.email)
    return {"access_token": token, "token_type": "bearer"}
```
"""
        )

        result = await agent.process_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert result.result["metrics"]["function_count"] > 0


class TestTestingAgent:
    """Test Testing Agent functionality."""

    @pytest.mark.asyncio
    async def test_create_testing_agent(self, llm_client, tool_registry, memory):
        """Test creating testing agent."""
        agent = await create_testing_agent(llm_client, tool_registry, memory)
        assert agent is not None
        assert agent.config.role == AgentRole.TESTING
        assert "testing" in agent.role_description.lower()

    @pytest.mark.asyncio
    async def test_process_testing_task(self, llm_client, tool_registry, memory):
        """Test processing test generation task."""
        agent = await create_testing_agent(llm_client, tool_registry, memory)

        task = AgentTask(
            id="test_001",
            role=AgentRole.TESTING,
            objective="Generate tests for authentication endpoint",
            context={"code": "login endpoint with JWT"},
        )

        llm_client.set_mock_response(
            """```python
import pytest
from fastapi.testclient import TestClient

def test_login_success():
    '''Test successful login with valid credentials.'''
    # Arrange
    client = TestClient(app)
    credentials = {"email": "user@example.com", "password": "password123"}

    # Act
    response = client.post("/auth/login", json=credentials)

    # Assert
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_invalid_credentials():
    '''Test login failure with invalid credentials.'''
    with pytest.raises(HTTPException):
        login(LoginRequest(email="invalid", password="wrong"))
```
"""
        )

        result = await agent.process_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert result.result["metrics"]["test_count"] > 0


class TestDeploymentAgent:
    """Test Deployment Agent functionality."""

    @pytest.mark.asyncio
    async def test_create_deployment_agent(self, llm_client, tool_registry, memory):
        """Test creating deployment agent."""
        agent = await create_deployment_agent(llm_client, tool_registry, memory)
        assert agent is not None
        assert agent.config.role == AgentRole.DEPLOYMENT
        assert "deployment" in agent.role_description.lower()

    @pytest.mark.asyncio
    async def test_process_deployment_task(self, llm_client, tool_registry, memory):
        """Test processing deployment automation task."""
        agent = await create_deployment_agent(llm_client, tool_registry, memory)

        task = AgentTask(
            id="deploy_001",
            role=AgentRole.DEPLOYMENT,
            objective="Create Kubernetes deployment for authentication service",
            context={"service": "auth-api", "replicas": 3},
        )

        llm_client.set_mock_response(
            """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: auth-api
        image: auth-api:latest
        resources:
          limits:
            cpu: "1"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
```
"""
        )

        result = await agent.process_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert result.result["quality_indicators"]["has_health_checks"]


class TestOperationsAgent:
    """Test Operations Agent functionality."""

    @pytest.mark.asyncio
    async def test_create_operations_agent(self, llm_client, tool_registry, memory):
        """Test creating operations agent."""
        agent = await create_operations_agent(llm_client, tool_registry, memory)
        assert agent is not None
        assert agent.config.role == AgentRole.OPERATIONS
        assert "operations" in agent.role_description.lower()

    @pytest.mark.asyncio
    async def test_process_operations_task(self, llm_client, tool_registry, memory):
        """Test processing operations monitoring task."""
        agent = await create_operations_agent(llm_client, tool_registry, memory)

        task = AgentTask(
            id="ops_001",
            role=AgentRole.OPERATIONS,
            objective="Set up monitoring for authentication service",
            context={"service": "auth-api", "metrics": "latency, errors, traffic"},
        )

        llm_client.set_mock_response(
            """```yaml
groups:
  - name: auth_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on auth service"
          runbook: "https://runbooks.example.com/auth-errors"

SLO: 99.9% availability for authentication service
```
"""
        )

        result = await agent.process_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.result is not None
        assert result.result["metrics"]["alert_rule_count"] > 0


class TestAgentOrchestrator:
    """Test Agent Orchestrator functionality."""

    @pytest.mark.asyncio
    async def test_create_orchestrator(self, llm_client, tool_registry, memory):
        """Test creating orchestrator with all agents."""
        orchestrator = await create_orchestrator(llm_client, tool_registry, memory)
        assert orchestrator is not None
        assert len(orchestrator.agents) == 6
        assert AgentRole.REQUIREMENTS in orchestrator.agents
        assert AgentRole.OPERATIONS in orchestrator.agents

    @pytest.mark.asyncio
    async def test_create_workflow(self, llm_client, tool_registry, memory):
        """Test creating a workflow."""
        orchestrator = await create_orchestrator(llm_client, tool_registry, memory)

        workflow = await orchestrator.create_workflow(
            name="Build Auth System",
            objective="Implement user authentication with JWT",
            stages=[WorkflowStage.REQUIREMENTS, WorkflowStage.ARCHITECTURE],
        )

        assert workflow.id is not None
        assert workflow.status == WorkflowStatus.PENDING
        assert len(workflow.stages) == 2

    @pytest.mark.asyncio
    async def test_execute_workflow(self, llm_client, tool_registry, memory):
        """Test executing full workflow."""
        orchestrator = await create_orchestrator(llm_client, tool_registry, memory)

        # Create simple workflow with two stages
        workflow = await orchestrator.create_workflow(
            name="Simple Auth",
            objective="Basic authentication system",
            stages=[WorkflowStage.REQUIREMENTS, WorkflowStage.ARCHITECTURE],
        )

        # Set mock responses for both stages
        llm_client.set_mock_response("As a user, I want to login. Must have.")
        llm_client.set_mock_response("Architecture: API Gateway, Auth Service")

        # Execute workflow
        result = await orchestrator.execute_workflow(workflow.id)

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.tasks) == 2
        assert all(task.status == TaskStatus.COMPLETED for task in result.tasks)

    @pytest.mark.asyncio
    async def test_workflow_context_propagation(self, llm_client, tool_registry, memory):
        """Test that workflow context propagates between stages."""
        orchestrator = await create_orchestrator(llm_client, tool_registry, memory)

        workflow = await orchestrator.create_workflow(
            name="Context Test",
            objective="Test context propagation",
            stages=[WorkflowStage.REQUIREMENTS, WorkflowStage.ARCHITECTURE],
            context={"initial": "data"},
        )

        llm_client.set_mock_response("Requirements output")
        llm_client.set_mock_response("Architecture output")

        result = await orchestrator.execute_workflow(workflow.id)

        # Check context was updated with stage results
        assert "requirements_result" in result.context
        assert "architecture_result" in result.context
        assert result.context["initial"] == "data"


class TestEndToEndSDLC:
    """Test end-to-end SDLC workflow."""

    @pytest.mark.asyncio
    async def test_full_sdlc_workflow(self, llm_client, tool_registry, memory):
        """Test complete SDLC workflow from requirements to operations."""
        orchestrator = await create_orchestrator(llm_client, tool_registry, memory)

        # Create full SDLC workflow
        workflow = await orchestrator.create_workflow(
            name="Complete SDLC",
            objective="Build and deploy user authentication system",
        )

        # Set mock responses for all stages
        mock_responses = [
            "As a user, I want to login with email/password",  # Requirements
            "Architecture: FastAPI + PostgreSQL + Redis",  # Architecture
            "def login(email, password): return jwt_token",  # Implementation
            "def test_login(): assert login() returns token",  # Testing
            "apiVersion: apps/v1\nkind: Deployment",  # Deployment
            "alert: HighLatency\nexpr: latency > 1s",  # Operations
        ]

        for response in mock_responses:
            llm_client.set_mock_response(response)

        # Execute full workflow
        result = await orchestrator.execute_workflow(workflow.id)

        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.tasks) == 6
        assert result.current_stage == WorkflowStage.OPERATIONS

        # Verify all stages completed
        completed_roles = [
            task.role for task in result.tasks if task.status == TaskStatus.COMPLETED
        ]
        assert AgentRole.REQUIREMENTS in completed_roles
        assert AgentRole.OPERATIONS in completed_roles
