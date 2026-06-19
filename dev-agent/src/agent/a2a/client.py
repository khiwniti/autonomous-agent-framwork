"""A2A Client for Inter-Agent Communication.

Provides HTTP client for communicating with other A2A-compliant agents,
enabling task delegation and multi-agent workflows.

Features:
- Agent discovery via /.well-known/agent.json
- Task creation with streaming support
- Session management for multi-turn conversations
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .agent_card import AgentCard, AgentSkill
from .task import Artifact, TaskMessage, TaskState, TaskStatus


class A2AResponse(BaseModel):
    """Response from A2A task operations."""
    
    task_id: str = Field(description="Task ID")
    session_id: str | None = Field(default=None)
    status: TaskStatus = Field(description="Task status")
    messages: list[TaskMessage] = Field(default=[])
    artifacts: list[Artifact] = Field(default=[])
    error: str | None = Field(default=None)


class A2AClient:
    """
    HTTP client for A2A agent communication.
    
    Enables agents to:
    - Discover other agents via Agent Cards
    - Send tasks to other agents
    - Stream task results
    - Manage multi-turn sessions
    
    Usage:
        async with A2AClient("http://agent.example.com") as client:
            # Discover agent
            card = await client.get_agent_card()
            print(f"Connected to: {card.name}")
            
            # Send task
            response = await client.send_task("Analyze requirements")
            
            # Or stream results
            async for event in client.send_task_streaming("Build feature"):
                print(event)
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 300.0,
        auth_token: str | None = None,
    ):
        """
        Initialize A2A client.
        
        Args:
            base_url: Agent's base URL
            timeout: Request timeout in seconds
            auth_token: Optional bearer token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token
        
        self._client: httpx.AsyncClient | None = None
        self._agent_card: AgentCard | None = None
    
    async def __aenter__(self) -> "A2AClient":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self) -> None:
        """Connect to the agent."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
        )
        
        # Fetch agent card on connect
        self._agent_card = await self.get_agent_card()
    
    async def disconnect(self) -> None:
        """Disconnect from the agent."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None
    
    @property
    def agent_card(self) -> AgentCard | None:
        """Get cached agent card."""
        return self._agent_card
    
    def _ensure_connected(self) -> httpx.AsyncClient:
        """Ensure client is connected and return it."""
        if not self._client:
            raise RuntimeError("Client not connected. Use 'async with' or call connect()")
        return self._client
    
    # =========================================================================
    # Discovery
    # =========================================================================
    
    async def get_agent_card(self) -> AgentCard:
        """
        Fetch Agent Card for capability discovery.
        
        Returns:
            AgentCard with agent capabilities
        """
        client = self._ensure_connected()
        response = await client.get("/.well-known/agent.json")
        response.raise_for_status()
        
        data = response.json()
        return AgentCard(**data)
    
    async def get_skills(self) -> list[AgentSkill]:
        """Get agent's available skills."""
        if not self._agent_card:
            self._agent_card = await self.get_agent_card()
        return self._agent_card.skills
    
    async def find_skill(self, skill_id: str) -> AgentSkill | None:
        """Find a specific skill by ID."""
        skills = await self.get_skills()
        for skill in skills:
            if skill.id == skill_id:
                return skill
        return None
    
    # =========================================================================
    # Task Operations
    # =========================================================================
    
    async def send_task(
        self,
        message: str,
        session_id: str | None = None,
        skill_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> A2AResponse:
        """
        Send a task to the agent (non-streaming).
        
        Waits for task completion before returning.
        
        Args:
            message: Task message/request
            session_id: Optional session for multi-turn
            skill_id: Target skill ID
            params: Additional parameters
            
        Returns:
            A2AResponse with task result
        """
        client = self._ensure_connected()
        
        payload = {
            "message": message,
            "session_id": session_id,
            "skill_id": skill_id,
            "params": params,
        }
        
        response = await client.post("/tasks/send", json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # Fetch full task state
        task_response = await client.get(f"/tasks/{data['id']}")
        task_response.raise_for_status()
        task_data = task_response.json()
        
        return A2AResponse(
            task_id=data["id"],
            session_id=data.get("session_id"),
            status=TaskStatus(data["status"]),
            messages=[TaskMessage(**m) for m in task_data.get("messages", [])],
            artifacts=[Artifact(**a) for a in task_data.get("artifacts", [])],
            error=task_data.get("error"),
        )
    
    async def send_task_streaming(
        self,
        message: str,
        session_id: str | None = None,
        skill_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Send a task with SSE streaming.
        
        Yields events as the task is processed.
        
        Args:
            message: Task message/request
            session_id: Optional session for multi-turn
            skill_id: Target skill ID
            params: Additional parameters
            
        Yields:
            Event dictionaries from SSE stream
        """
        client = self._ensure_connected()
        
        payload = {
            "message": message,
            "session_id": session_id,
            "skill_id": skill_id,
            "params": params,
        }
        
        async with client.stream(
            "POST",
            "/tasks/sendSubscribe",
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            
            event_name = None
            event_data = []
            
            async for line in response.aiter_lines():
                line = line.strip()
                
                if not line:
                    # End of event
                    if event_name and event_data:
                        try:
                            data = json.loads("\n".join(event_data))
                            yield {"event": event_name, "data": data}
                        except json.JSONDecodeError:
                            pass
                    event_name = None
                    event_data = []
                
                elif line.startswith("event:"):
                    event_name = line[6:].strip()
                
                elif line.startswith("data:"):
                    event_data.append(line[5:].strip())
    
    async def get_task(self, task_id: str) -> TaskState | None:
        """
        Get task status and details.
        
        Args:
            task_id: Task ID
            
        Returns:
            TaskState or None if not found
        """
        client = self._ensure_connected()
        
        try:
            response = await client.get(f"/tasks/{task_id}")
            response.raise_for_status()
            return TaskState(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if canceled successfully
        """
        client = self._ensure_connected()
        
        try:
            response = await client.post(f"/tasks/{task_id}/cancel")
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
    
    async def provide_input(self, task_id: str, user_input: str) -> bool:
        """
        Provide input for a paused task (human-in-the-loop).
        
        Args:
            task_id: Task ID
            user_input: User's response
            
        Returns:
            True if input accepted
        """
        client = self._ensure_connected()
        
        try:
            response = await client.post(
                f"/tasks/{task_id}/input",
                json={"input": user_input},
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
    
    # =========================================================================
    # Health Checks
    # =========================================================================
    
    async def health_check(self) -> bool:
        """Check if agent is healthy."""
        client = self._ensure_connected()
        
        try:
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def ready_check(self) -> bool:
        """Check if agent is ready to receive tasks."""
        client = self._ensure_connected()
        
        try:
            response = await client.get("/ready")
            return response.status_code == 200
        except Exception:
            return False


class A2AAgentRegistry:
    """
    Registry for discovering and managing A2A agents.
    
    Provides:
    - Agent discovery by skill/capability
    - Connection pooling
    - Load balancing (future)
    
    Usage:
        registry = A2AAgentRegistry()
        await registry.register("http://requirements-agent:8000")
        await registry.register("http://coding-agent:8001")
        
        # Find agent by skill
        client = await registry.find_agent_by_skill("analyze-requirements")
    """
    
    def __init__(self):
        self._agents: dict[str, A2AClient] = {}
        self._skill_index: dict[str, list[str]] = {}  # skill_id -> agent URLs
    
    async def register(self, url: str, auth_token: str | None = None) -> AgentCard:
        """
        Register an agent by URL.
        
        Args:
            url: Agent's base URL
            auth_token: Optional auth token
            
        Returns:
            Agent's AgentCard
        """
        client = A2AClient(url, auth_token=auth_token)
        await client.connect()
        
        self._agents[url] = client
        
        # Index skills
        for skill in client.agent_card.skills:
            if skill.id not in self._skill_index:
                self._skill_index[skill.id] = []
            self._skill_index[skill.id].append(url)
        
        return client.agent_card
    
    async def unregister(self, url: str) -> None:
        """Unregister an agent."""
        if url in self._agents:
            client = self._agents.pop(url)
            await client.disconnect()
            
            # Remove from skill index
            for skill_id, urls in self._skill_index.items():
                if url in urls:
                    urls.remove(url)
    
    async def find_agent_by_skill(self, skill_id: str) -> A2AClient | None:
        """
        Find an agent that provides a specific skill.
        
        Args:
            skill_id: Skill ID to search for
            
        Returns:
            A2AClient or None if no agent found
        """
        urls = self._skill_index.get(skill_id, [])
        if urls:
            # Simple round-robin (could implement load balancing)
            url = urls[0]
            return self._agents.get(url)
        return None
    
    async def find_agents_by_capability(
        self,
        capability: str,
    ) -> list[A2AClient]:
        """
        Find all agents with a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of A2AClients
        """
        matching = []
        for client in self._agents.values():
            if client.agent_card and client.agent_card.capabilities.get(capability):
                matching.append(client)
        return matching
    
    def get_all_agents(self) -> list[A2AClient]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    async def close(self) -> None:
        """Close all agent connections."""
        for client in self._agents.values():
            await client.disconnect()
        self._agents.clear()
        self._skill_index.clear()
