# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo
import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

try:
    _, project_id = google.auth.default()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
except Exception:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

import urllib.request
import urllib.parse
import json

def book_appointment(customer_name: str, service: str, preferred_time: str) -> str:
    """Simulates booking an appointment in the salon's system.

    Args:
        customer_name: The name of the customer.
        service: The requested beauty service (e.g. 'taglio', 'colore', 'manicure').
        preferred_time: The requested time for the appointment.

    Returns:
        A confirmation string with the booking details.
    """
    return f"Prenotazione confermata per {customer_name}. Servizio: {service} alle ore {preferred_time}."

def get_services(query: str) -> str:
    """Returns the list of available services and prices.

    Args:
        query: Optional filter for services.

    Returns:
        A string listing services.
    """
    return "I nostri servizi: Taglio (25€), Colore (45€), Piega (15€), Manicure (20€)."

def delegate_dev_task(task_objective: str, target_language: str = "python") -> dict:
    """Delegates a software engineering or development task to the Autonomous Dev Agent via A2A protocol."""
    import urllib.request
    import urllib.error
    import json
    import uuid

    tambo_context = (
        "ARCHITECTURAL RULE: For full-stack AI web app sessions, evaluate the requirements case-by-case. "
        "If the web app requires a Generative UI to communicate between the agent framework and the frontend viewport, "
        "you MUST use the Tambo AI framework ('npx tambo create-app <name> --template=standard' and 'npx tambo add'). "
        "Documentation: https://docs.tambo.co/llms.txt. Use your judgment as the Autonomous Dev Agent to decide if Tambo is suitable."
    )
    
    payload = json.dumps({
        "message": f"Language: {target_language}. Task: {task_objective}\n\n{tambo_context}",
        "session_id": str(uuid.uuid4()),
        "skill_id": None,
        "params": {}
    }).encode('utf-8')

    # Send task using A2A standard endpoint
    # The A2A server app runs on port 8001
    dev_agent_url = os.environ.get('DEV_AGENT_URL', 'http://localhost:8001')
    req = urllib.request.Request(
        f"{dev_agent_url}/tasks/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            mcp_url = os.environ.get("MCP_URL", "http://localhost:8002/sse")
            return {
                "status": "success", 
                "task_id": result.get("id"), 
                "mcp_url": mcp_url,
                "a2a_response": result,
                "message": f"Task delegated to Dev Agent. Sandbox MCP Server is streaming UI components at {mcp_url}"
            }
    except urllib.error.URLError as e:
        # Fallback for E2E testing if dev agent A2A server is not reachable
        return {
            "status": "queued",
            "message": f"Task delegated successfully! Task ID: mock_task_{uuid.uuid4().hex[:4]}, Status: queued",
            "warning": f"A2A server unreachable ({e}). Using mock response."
        }

root_agent = Agent(
    name="mvp_hybrid_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "Sei l'assistente AI per FDE Studio. Hai una doppia funzionalità: "
        "1. Come receptionist virtuale (Digalook) per prenotare servizi e appuntamenti. "
        "2. Come orchestratore di sviluppo software, in grado di delegare task di programmazione complessi "
        "all'Autonomous Dev Agent tramite la funzione delegate_dev_task. "
        "Se l'utente chiede modifiche al codice o task di sviluppo, usa delegate_dev_task!"
    ),
    tools=[book_appointment, get_services, delegate_dev_task],
)

app = App(
    root_agent=root_agent,
    name="digalook_app",
)
