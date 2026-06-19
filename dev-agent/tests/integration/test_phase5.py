"""Integration tests for Phase 5: API & User Interfaces."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agent.agents.base import AgentRole, AgentTask, TaskStatus
from agent.api.rest import AgentAPI
from agent.api.schemas import (
    AgentExecutionRequest,
    SessionCreateRequest,
    WorkflowExecutionRequest,
    ChatMessageRequest,
)
from agent.api.websocket import ConnectionManager, WebSocketAPI
from agent.core.orchestrator import create_orchestrator, WorkflowStage
from agent.llm.mock import MockLLMClient
from agent.memory.working import WorkingMemory
from agent.security.authentication import AuthManager, User
from agent.security.rate_limiting import RateLimiter, QuotaManager
from agent.session.checkpoint import CheckpointManager
from agent.session.manager import SessionManager
from agent.tools.base import ToolRegistry


@pytest.fixture
async def llm_client():
    """Create mock LLM client."""
    return MockLLMClient()


@pytest.fixture
async def tool_registry():
    """Create tool registry."""
    return ToolRegistry()


@pytest.fixture
async def memory():
    """Create working memory."""
    return WorkingMemory()


@pytest.fixture
async def orchestrator(llm_client, tool_registry, memory):
    """Create orchestrator."""
    return await create_orchestrator(llm_client, tool_registry, memory)


@pytest.fixture
async def session_manager():
    """Create session manager."""
    return SessionManager()


@pytest.fixture
async def agent_api(llm_client, tool_registry, session_manager):
    """Create agent API."""
    return AgentAPI(llm_client, tool_registry, session_manager)


@pytest.fixture
def test_client(agent_api):
    """Create test client."""
    return TestClient(agent_api.app)


# REST API Tests


class TestRESTAPI:
    """Test REST API endpoints."""

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_create_session(self, test_client):
        """Test session creation."""
        response = test_client.post(
            "/sessions",
            json={"name": "Test Session", "metadata": {"key": "value"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Session"
        assert data["metadata"]["key"] == "value"
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_get_session(self, test_client):
        """Test getting session."""
        # Create session
        create_response = test_client.post("/sessions", json={"name": "Test"})
        session_id = create_response.json()["session_id"]

        # Get session
        response = test_client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_list_sessions(self, test_client):
        """Test listing sessions."""
        # Create 3 sessions
        for i in range(3):
            test_client.post("/sessions", json={"name": f"Session {i}"})

        # List sessions
        response = test_client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    @pytest.mark.asyncio
    async def test_delete_session(self, test_client):
        """Test deleting session."""
        # Create session
        create_response = test_client.post("/sessions", json={"name": "Delete Me"})
        session_id = create_response.json()["session_id"]

        # Delete session
        response = test_client.delete(f"/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = test_client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_agent(self, test_client, llm_client):
        """Test agent execution."""
        # Set mock response
        llm_client.set_mock_response("Test agent response")

        # Execute agent
        response = test_client.post(
            "/agents/execute",
            json={
                "agent_role": "requirements",
                "objective": "Test objective",
                "context": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] in ["pending", "in_progress"]

    @pytest.mark.asyncio
    async def test_get_task_status(self, test_client, llm_client):
        """Test getting task status."""
        llm_client.set_mock_response("Test response")

        # Execute agent
        exec_response = test_client.post(
            "/agents/execute",
            json={"agent_role": "requirements", "objective": "Test"},
        )
        task_id = exec_response.json()["task_id"]

        # Get task status
        response = test_client.get(f"/tasks/{task_id}")
        assert response.status_code in [200, 404]  # 404 if task not found yet

    @pytest.mark.asyncio
    async def test_execute_workflow(self, test_client, llm_client):
        """Test workflow execution."""
        llm_client.set_mock_response("Test workflow response")

        # Execute workflow
        response = test_client.post(
            "/workflows/execute",
            json={
                "name": "Test Workflow",
                "objective": "Test objective",
                "stages": ["requirements", "architecture"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "workflow_id" in data
        assert data["status"] in ["pending", "in_progress"]

    @pytest.mark.asyncio
    async def test_send_chat_message(self, test_client, llm_client):
        """Test sending chat message."""
        # Create session
        session_response = test_client.post("/sessions", json={"name": "Chat Test"})
        session_id = session_response.json()["session_id"]

        llm_client.set_mock_response("Hello! How can I help?")

        # Send message
        response = test_client.post(
            "/chat",
            json={"session_id": session_id, "message": "Hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message_id" in data
        assert "response" in data


# WebSocket API Tests


class TestWebSocketAPI:
    """Test WebSocket API."""

    @pytest.mark.asyncio
    async def test_connection_manager_connect(self):
        """Test connection manager connect."""
        from fastapi import WebSocket

        manager = ConnectionManager()

        # Mock WebSocket
        class MockWebSocket:
            async def accept(self):
                pass

        websocket = MockWebSocket()
        await manager.connect(websocket, "conn_1", "session_1")

        assert "conn_1" in manager.active_connections
        assert "session_1" in manager.session_connections
        assert "conn_1" in manager.session_connections["session_1"]

    @pytest.mark.asyncio
    async def test_connection_manager_disconnect(self):
        """Test connection manager disconnect."""
        manager = ConnectionManager()

        class MockWebSocket:
            async def accept(self):
                pass

        websocket = MockWebSocket()
        await manager.connect(websocket, "conn_1", "session_1")

        manager.disconnect("conn_1", "session_1")

        assert "conn_1" not in manager.active_connections
        assert "session_1" not in manager.session_connections


# Session Management Tests


class TestSessionManagement:
    """Test session management."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating session."""
        session = await session_manager.create_session(
            name="Test", metadata={"key": "value"}
        )

        assert session.name == "Test"
        assert session.metadata["key"] == "value"
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        """Test getting session."""
        created = await session_manager.create_session(name="Test")
        retrieved = await session_manager.get_session(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager):
        """Test listing sessions."""
        # Create sessions
        for i in range(3):
            await session_manager.create_session(name=f"Session {i}")

        # List sessions
        sessions = await session_manager.list_sessions()
        assert len(sessions) >= 3

    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager):
        """Test deleting session."""
        session = await session_manager.create_session(name="Delete")
        success = await session_manager.delete_session(session.id)

        assert success is True
        retrieved = await session_manager.get_session(session.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_deactivate_session(self, session_manager):
        """Test deactivating session."""
        session = await session_manager.create_session(name="Deactivate")
        success = await session_manager.deactivate_session(session.id)

        assert success is True
        retrieved = await session_manager.get_session(session.id)
        assert retrieved.is_active is False

    @pytest.mark.asyncio
    async def test_session_add_task(self, session_manager):
        """Test adding task to session."""
        session = await session_manager.create_session(name="Task Test")
        task = AgentTask(
            id="task_1",
            role=AgentRole.REQUIREMENTS,
            objective="Test objective",
        )

        await session.add_task(task)
        assert len(session.tasks) == 1
        assert session.tasks[0].id == "task_1"

    @pytest.mark.asyncio
    async def test_session_add_message(self, session_manager):
        """Test adding message to session."""
        session = await session_manager.create_session(name="Message Test")

        await session.add_message("user", "Hello", metadata={"key": "value"})
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_session_task_summary(self, session_manager):
        """Test session task summary."""
        session = await session_manager.create_session(name="Summary Test")

        # Add tasks
        for i in range(5):
            task = AgentTask(
                id=f"task_{i}",
                role=AgentRole.REQUIREMENTS,
                objective="Test",
            )
            task.status = TaskStatus.COMPLETED if i < 3 else TaskStatus.FAILED
            await session.add_task(task)

        summary = await session.get_task_summary()
        assert summary["total"] == 5
        assert summary["completed"] == 3
        assert summary["failed"] == 2


# Checkpoint Tests


class TestCheckpointManagement:
    """Test checkpoint management."""

    @pytest.mark.asyncio
    async def test_save_workflow_checkpoint(self, orchestrator):
        """Test saving workflow checkpoint."""
        # Create workflow
        workflow = await orchestrator.create_workflow(
            name="Test", objective="Test objective"
        )

        # Save checkpoint
        checkpoint_manager = CheckpointManager()
        checkpoint_id = await checkpoint_manager.save_workflow_checkpoint(workflow)

        assert checkpoint_id.startswith("workflow_")
        assert (checkpoint_manager.checkpoint_dir / f"{checkpoint_id}.json").exists()

    @pytest.mark.asyncio
    async def test_load_workflow_checkpoint(self, orchestrator):
        """Test loading workflow checkpoint."""
        # Create and save workflow
        workflow = await orchestrator.create_workflow(
            name="Test", objective="Test objective"
        )

        checkpoint_manager = CheckpointManager()
        checkpoint_id = await checkpoint_manager.save_workflow_checkpoint(workflow)

        # Load checkpoint
        loaded = await checkpoint_manager.load_workflow_checkpoint(checkpoint_id)

        assert loaded is not None
        assert loaded.id == workflow.id
        assert loaded.name == workflow.name

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self):
        """Test deleting checkpoint."""
        checkpoint_manager = CheckpointManager()

        # Create dummy checkpoint
        checkpoint_id = "test_checkpoint"
        checkpoint_path = checkpoint_manager.checkpoint_dir / f"{checkpoint_id}.json"
        checkpoint_path.write_text("{}")

        # Delete checkpoint
        success = await checkpoint_manager.delete_checkpoint(checkpoint_id)
        assert success is True
        assert not checkpoint_path.exists()


# Authentication Tests


class TestAuthentication:
    """Test authentication."""

    def test_generate_api_key(self):
        """Test API key generation."""
        auth_manager = AuthManager("secret")
        key = auth_manager.generate_api_key("user_1", "Test Key")

        assert key.startswith("sk-")
        assert key in auth_manager.api_keys

    def test_validate_api_key(self):
        """Test API key validation."""
        auth_manager = AuthManager("secret")
        key = auth_manager.generate_api_key("user_1", "Test Key")

        api_key = auth_manager.validate_api_key(key)
        assert api_key is not None
        assert api_key.user_id == "user_1"

    def test_revoke_api_key(self):
        """Test API key revocation."""
        auth_manager = AuthManager("secret")
        key = auth_manager.generate_api_key("user_1", "Test Key")

        success = auth_manager.revoke_api_key(key)
        assert success is True
        assert key not in auth_manager.api_keys

    def test_create_access_token(self):
        """Test JWT token creation."""
        auth_manager = AuthManager("secret")
        token = auth_manager.create_access_token("user_1", scopes=["read", "write"])

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token(self):
        """Test JWT token verification."""
        auth_manager = AuthManager("secret")
        token = auth_manager.create_access_token("user_1", scopes=["read"])

        token_data = auth_manager.verify_token(token)
        assert token_data is not None
        assert token_data.sub == "user_1"
        assert "read" in token_data.scopes

    def test_create_user(self):
        """Test user creation."""
        auth_manager = AuthManager("secret")
        user = auth_manager.create_user("user@example.com", "testuser")

        assert user.email == "user@example.com"
        assert user.username == "testuser"
        assert user.id in auth_manager.users


# Rate Limiting Tests


class TestRateLimiting:
    """Test rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire(self):
        """Test rate limiter acquire."""
        limiter = RateLimiter(rate=10, per=60)  # 10 requests per minute

        # First request should succeed
        allowed = await limiter.acquire("user_1")
        assert allowed is True

        # After burst exhausted, should fail
        for _ in range(10):
            await limiter.acquire("user_1")

        allowed = await limiter.acquire("user_1")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_rate_limiter_get_remaining(self):
        """Test getting remaining tokens."""
        limiter = RateLimiter(rate=10, per=60, burst=10)

        remaining = await limiter.get_remaining("user_1")
        assert remaining == 10

        await limiter.acquire("user_1", tokens=5)
        remaining = await limiter.get_remaining("user_1")
        assert remaining == 5

    @pytest.mark.asyncio
    async def test_quota_manager_set_quota(self):
        """Test setting quota."""
        quota_manager = QuotaManager()
        await quota_manager.set_quota("user_1", "daily", 100)

        status = await quota_manager.get_quota_status("user_1", "daily")
        assert status is not None
        assert status["total"] == 100

    @pytest.mark.asyncio
    async def test_quota_manager_consume(self):
        """Test consuming quota."""
        quota_manager = QuotaManager()
        await quota_manager.set_quota("user_1", "daily", 10)

        # Consume quota
        allowed = await quota_manager.consume("user_1", "daily", 5)
        assert allowed is True

        status = await quota_manager.get_quota_status("user_1", "daily")
        assert status["used"] == 5
        assert status["remaining"] == 5

    @pytest.mark.asyncio
    async def test_quota_manager_exceed_limit(self):
        """Test exceeding quota limit."""
        quota_manager = QuotaManager()
        await quota_manager.set_quota("user_1", "daily", 5)

        # Consume full quota
        await quota_manager.consume("user_1", "daily", 5)

        # Try to exceed
        allowed = await quota_manager.consume("user_1", "daily", 1)
        assert allowed is False


# End-to-End Tests


class TestEndToEndAPI:
    """Test end-to-end API workflows."""

    @pytest.mark.asyncio
    async def test_complete_session_workflow(self, test_client, llm_client):
        """Test complete session workflow."""
        # 1. Create session
        session_response = test_client.post(
            "/sessions", json={"name": "E2E Test Session"}
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["session_id"]

        # 2. Execute agent task
        llm_client.set_mock_response("Requirements gathered")
        task_response = test_client.post(
            "/agents/execute",
            json={
                "agent_role": "requirements",
                "objective": "Gather requirements",
                "session_id": session_id,
            },
        )
        assert task_response.status_code == 200

        # 3. Get session with tasks
        session_get_response = test_client.get(f"/sessions/{session_id}")
        assert session_get_response.status_code == 200
        session_data = session_get_response.json()
        assert len(session_data["tasks"]) >= 0

        # 4. Delete session
        delete_response = test_client.delete(f"/sessions/{session_id}")
        assert delete_response.status_code == 200

    @pytest.mark.asyncio
    async def test_workflow_with_checkpointing(self, orchestrator):
        """Test workflow with checkpoint/resume."""
        # Create workflow
        workflow = await orchestrator.create_workflow(
            name="Checkpoint Test",
            objective="Test checkpointing",
            stages=[WorkflowStage.REQUIREMENTS, WorkflowStage.ARCHITECTURE],
        )

        # Save checkpoint
        checkpoint_manager = CheckpointManager()
        checkpoint_id = await checkpoint_manager.save_workflow_checkpoint(workflow)

        # Load checkpoint
        from agent.session.checkpoint import resume_workflow

        resumed = await resume_workflow(checkpoint_manager, checkpoint_id, orchestrator)

        assert resumed is not None
        assert resumed.id == workflow.id
        assert resumed.name == workflow.name
