import asyncio
from agent.a2a.server import A2AServer
from agent.a2a.agent_card import AgentCard, get_skills_for_phase
from agent.a2a.task import TaskState
from typing import AsyncGenerator
from fastapi import FastAPI
import uvicorn

async def task_handler(state: TaskState) -> AsyncGenerator[TaskState, None]:
    yield state

def create_a2a_app() -> FastAPI:
    card = AgentCard(
        name="Autonomous Dev Agent",
        description="Autonomous Software Development Agent over A2A",
        url="http://localhost:8001",
        version="1.0.0",
        skills=get_skills_for_phase("coding")
    )
    server = A2AServer(agent_card=card, task_handler=task_handler)
    return server.app

if __name__ == "__main__":
    app = create_a2a_app()
    uvicorn.run(app, host="0.0.0.0", port=8001)
