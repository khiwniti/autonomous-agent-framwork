#!/bin/bash

# Start the REST API
python -m uvicorn agent.api.rest:app --host 0.0.0.0 --port 8000 &

# Start the A2A JSON-RPC Server
python src/agent/api/a2a_app.py &

# Start the Sandbox MCP Server
python src/agent/mcp/sandbox_server.py &

# Wait for all background processes
wait
